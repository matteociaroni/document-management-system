"""
Agent Worker — main loop.

Polls the DB every POLL_INTERVAL seconds and processes two distinct queues:

  1. EmailJob records with status='pending' — produced by the email_poller.
     For each job: download the .eml, extract attachments, file them.

  2. EmailAttachment records with source='manual_upload' and status='pending' —
     produced by the backend's POST /documents/upload-ai endpoint.
     For each attachment: download the document from S3, classify it through
     the same filing agent and apply the same confidence threshold (auto_filed
     vs in_inbox), so the user-facing semantics are uniform.
"""

import hashlib
import logging
import time
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from config import settings
from agent import run_filing_agent
from database import SessionLocal
from eml_parser import extract_text_preview, parse_email
from models import AgentOperation, Document, EmailAccount, EmailAttachment, EmailJob, User
from storage import ensure_bucket, get_bucket_name, get_s3_client, load_document, load_eml, EML_BUCKET

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("agent_worker")


def _get_pending_jobs(db: Session) -> list[EmailJob]:
    return (
        db.query(EmailJob)
        .filter(EmailJob.status == "pending")
        .order_by(EmailJob.created_at.asc())
        .limit(10)
        .all()
    )


def _log_op(
    db: Session,
    user_id: UUID,
    job_id: UUID | None,
    attachment_id: UUID | None,
    op_type: str,
    description: str,
    details: dict | None = None,
) -> None:
    op = AgentOperation(
        user_id=user_id,
        job_id=job_id,
        attachment_id=attachment_id,
        operation_type=op_type,
        description=description,
        details=details,
    )
    db.add(op)


def _process_job(db: Session, job: EmailJob) -> None:
    logger.info("Processing job %s (uid=%d)", job.id, job.message_uid)

    # Resolve user through the email account
    account: EmailAccount = (
        db.query(EmailAccount)
        .filter(EmailAccount.id == job.email_account_id)
        .first()
    )
    user: User = db.query(User).filter(User.id == account.user_id).first()

    # Download and parse the .eml
    if not job.eml_storage_key:
        raise ValueError(f"Job {job.id} has no eml_storage_key")

    raw_bytes = load_eml(job.eml_storage_key)
    parsed = parse_email(raw_bytes)
    parsed_attachments = parsed.attachments

    if not parsed_attachments:
        logger.info("Job %s has no attachments — marking done", job.id)
        job.status = "done"
        job.processed_at = datetime.now(timezone.utc)
        db.commit()
        return

    # Upload attachments to SeaweedFS and create Document + EmailAttachment records
    s3 = get_s3_client()
    bucket = get_bucket_name(user.email)
    ensure_bucket(s3, bucket)

    records: list[tuple] = []  # (ParsedAttachment, EmailAttachment, Document)

    for att in parsed_attachments:
        content_hash = hashlib.sha256(att.content).hexdigest()

        doc = Document(
            name=att.filename,
            mime_type=att.mime_type,
            size_bytes=att.size_bytes,
            folder_id=None,
            owner_id=user.id,
        )
        db.add(doc)
        db.flush()

        s3.put_object(Bucket=bucket, Key=str(doc.id), Body=att.content)

        email_att = EmailAttachment(
            job_id=job.id,
            filename=att.filename,
            mime_type=att.mime_type,
            size_bytes=att.size_bytes,
            content_hash=content_hash,
            document_id=doc.id,
            status="pending",
        )
        db.add(email_att)
        db.flush()

        _log_op(
            db,
            user_id=user.id,
            job_id=job.id,
            attachment_id=email_att.id,
            op_type="attachment_extracted",
            description=f"Allegato estratto: '{att.filename}'",
            details={"mime_type": att.mime_type, "size_bytes": att.size_bytes},
        )
        records.append((att, email_att, doc))

    db.commit()
    logger.info("Uploaded %d attachment(s) for job %s", len(records), job.id)

    # Run CrewAI crew
    attachment_dicts = [
        {
            "filename": att.filename,
            "mime_type": att.mime_type,
            "size_bytes": att.size_bytes,
            "text_preview": att.text_preview,
        }
        for att, _, _ in records
    ]

    result = run_filing_agent(
        user_id=str(user.id),
        context_title=job.subject or "(no subject)",
        context_source=job.sender or "(unknown sender)",
        context_description=parsed.body_text,
        attachments=attachment_dicts,
    )

    decisions_by_filename = {d.filename: d for d in result.decisions}

    for att, email_att, doc in records:
        decision = decisions_by_filename.get(att.filename)

        if not decision:
            email_att.status = "in_inbox"
            _log_op(
                db,
                user_id=user.id,
                job_id=job.id,
                attachment_id=email_att.id,
                op_type="sent_to_inbox",
                description=f"'{att.filename}' inviato in inbox (nessuna decisione dall'agente)",
            )
            continue

        folder_uuid = None
        if decision.folder_id:
            try:
                folder_uuid = UUID(decision.folder_id)
            except ValueError:
                logger.warning("Invalid folder_id from agent: %s", decision.folder_id)

        email_att.suggested_folder_id = folder_uuid
        email_att.confidence = decision.confidence
        email_att.agent_reasoning = decision.reasoning

        if folder_uuid and decision.confidence >= settings.auto_file_threshold:
            email_att.status = "auto_filed"
            email_att.auto_filed = True
            doc.folder_id = folder_uuid
            _log_op(
                db,
                user_id=user.id,
                job_id=job.id,
                attachment_id=email_att.id,
                op_type="auto_filed",
                description=(
                    f"Archiviato automaticamente '{att.filename}' "
                    f"(confidence: {decision.confidence:.0%})"
                ),
                details={"folder_id": str(folder_uuid), "confidence": decision.confidence},
            )
        else:
            email_att.status = "in_inbox"
            _log_op(
                db,
                user_id=user.id,
                job_id=job.id,
                attachment_id=email_att.id,
                op_type="sent_to_inbox",
                description=(
                    f"'{att.filename}' inviato in inbox per revisione "
                    f"(confidence: {decision.confidence:.0%})"
                ),
                details={"folder_id": str(folder_uuid) if folder_uuid else None, "confidence": decision.confidence},
            )

    job.status = "done"
    job.processed_at = datetime.now(timezone.utc)
    db.commit()
    logger.info("Job %s completed", job.id)


def _process_job_safe(db: Session, job: EmailJob) -> None:
    """Wrap _process_job with error handling that marks the job as failed."""
    try:
        job.status = "processing"
        db.commit()
        _process_job(db, job)
    except Exception as e:
        db.rollback()
        logger.error("Job %s failed: %s", job.id, e, exc_info=True)
        try:
            job.status = "failed"
            job.error_message = str(e)
            job.processed_at = datetime.now(timezone.utc)
            db.commit()
        except Exception:
            db.rollback()


def _get_pending_manual_uploads(db: Session) -> list[EmailAttachment]:
    return (
        db.query(EmailAttachment)
        .filter(
            EmailAttachment.source == "manual_upload",
            EmailAttachment.status == "pending",
        )
        .order_by(EmailAttachment.created_at.asc())
        .limit(10)
        .all()
    )


def _process_manual_upload(db: Session, attachment: EmailAttachment) -> None:
    """Classify a user-uploaded document through the filing agent.

    The flow mirrors _process_job but starts from an already-stored Document:
    no .eml to parse, no email metadata. The filing agent is invoked with
    a synthetic 'email' context so the existing prompt continues to work."""
    logger.info("Processing manual upload %s ('%s')", attachment.id, attachment.filename)

    doc: Document = (
        db.query(Document).filter(Document.id == attachment.document_id).first()
    )
    if not doc:
        raise ValueError(f"Attachment {attachment.id} has no associated document")

    user: User = db.query(User).filter(User.id == doc.owner_id).first()
    if not user:
        raise ValueError(f"Document {doc.id} owner not found")

    # Pull bytes from the tenant bucket and extract a text preview using the
    # same logic that powers the email pipeline.
    bucket = get_bucket_name(user.email)
    content = load_document(bucket, str(doc.id))
    text_preview = extract_text_preview(content, attachment.mime_type, attachment.filename)

    result = run_filing_agent(
        user_id=str(user.id),
        context_title=attachment.filename,
        context_source="(manual upload)",
        context_description=None,
        attachments=[{
            "filename": attachment.filename,
            "mime_type": attachment.mime_type or "application/octet-stream",
            "size_bytes": attachment.size_bytes or len(content),
            "text_preview": text_preview,
        }],
    )

    decision = next(
        (d for d in result.decisions if d.filename == attachment.filename),
        None,
    )

    if not decision:
        attachment.status = "in_inbox"
        _log_op(
            db,
            user_id=user.id,
            job_id=None,
            attachment_id=attachment.id,
            op_type="sent_to_inbox",
            description=f"'{attachment.filename}' inviato in inbox (nessuna decisione dall'agente)",
        )
        db.commit()
        return

    folder_uuid = None
    if decision.folder_id:
        try:
            folder_uuid = UUID(decision.folder_id)
        except ValueError:
            logger.warning("Invalid folder_id from agent: %s", decision.folder_id)

    attachment.suggested_folder_id = folder_uuid
    attachment.confidence = decision.confidence
    attachment.agent_reasoning = decision.reasoning

    if folder_uuid and decision.confidence >= settings.auto_file_threshold:
        attachment.status = "auto_filed"
        attachment.auto_filed = True
        doc.folder_id = folder_uuid
        _log_op(
            db,
            user_id=user.id,
            job_id=None,
            attachment_id=attachment.id,
            op_type="auto_filed",
            description=(
                f"Archiviato automaticamente '{attachment.filename}' "
                f"(confidence: {decision.confidence:.0%})"
            ),
            details={"folder_id": str(folder_uuid), "confidence": decision.confidence},
        )
    else:
        attachment.status = "in_inbox"
        _log_op(
            db,
            user_id=user.id,
            job_id=None,
            attachment_id=attachment.id,
            op_type="sent_to_inbox",
            description=(
                f"'{attachment.filename}' inviato in inbox per revisione "
                f"(confidence: {decision.confidence:.0%})"
            ),
            details={
                "folder_id": str(folder_uuid) if folder_uuid else None,
                "confidence": decision.confidence,
            },
        )

    db.commit()


def _process_manual_upload_safe(db: Session, attachment: EmailAttachment) -> None:
    """Wrap _process_manual_upload so a failure on one item never stops the loop."""
    try:
        _process_manual_upload(db, attachment)
    except Exception as e:
        db.rollback()
        logger.error("Manual upload %s failed: %s", attachment.id, e, exc_info=True)
        try:
            # Refresh the attachment after rollback before mutating it.
            attachment = (
                db.query(EmailAttachment)
                .filter(EmailAttachment.id == attachment.id)
                .first()
            )
            if attachment is not None:
                attachment.status = "in_inbox"
                attachment.agent_reasoning = (
                    "Classificazione fallita: l'agente non ha potuto processare il file. "
                    "Sposta manualmente il documento nella cartella desiderata."
                )
                db.add(AgentOperation(
                    user_id=db.query(Document.owner_id)
                              .filter(Document.id == attachment.document_id)
                              .scalar(),
                    job_id=None,
                    attachment_id=attachment.id,
                    operation_type="error",
                    description=f"Classificazione fallita per '{attachment.filename}': {e}",
                    details={"error": str(e)},
                ))
                db.commit()
        except Exception:
            db.rollback()


def run_worker() -> None:
    logger.info(
        "Agent worker started. Poll interval: %ds, auto-file threshold: %.0f%%",
        settings.poll_interval_seconds,
        settings.auto_file_threshold * 100,
    )

    # Ensure EML bucket exists at startup
    s3 = get_s3_client()
    ensure_bucket(s3, EML_BUCKET)
    logger.info("EML bucket '%s' is ready", EML_BUCKET)

    while True:
        db: Session = SessionLocal()
        try:
            jobs = _get_pending_jobs(db)
            if jobs:
                logger.info("Found %d pending email job(s)", len(jobs))
            for job in jobs:
                _process_job_safe(db, job)

            manual_uploads = _get_pending_manual_uploads(db)
            if manual_uploads:
                logger.info("Found %d pending manual upload(s)", len(manual_uploads))
            for attachment in manual_uploads:
                _process_manual_upload_safe(db, attachment)
        except Exception as e:
            logger.error("Unexpected error in poll cycle: %s", e, exc_info=True)
        finally:
            db.close()

        time.sleep(settings.poll_interval_seconds)


if __name__ == "__main__":
    run_worker()
