"""
Agent Worker — main loop.

Polls the DB every POLL_INTERVAL seconds for pending EmailJob records.
For each job:
  1. Downloads the .eml from SeaweedFS.
  2. Extracts attachments and uploads them as Document records.
  3. Runs the Atomic Agents filing agent to decide where each attachment belongs.
  4. Writes the decisions back to EmailAttachment records.
  5. Marks the job as done (or failed on error).
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
from eml_parser import parse_email
from models import AgentOperation, Document, EmailAccount, EmailAttachment, EmailJob, User
from storage import ensure_bucket, get_bucket_name, get_s3_client, load_eml, EML_BUCKET

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
    job_id: UUID,
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
    email_body = parsed.body_text
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
        email_subject=job.subject or "(no subject)",
        email_sender=job.sender or "(unknown sender)",
        email_body=email_body,
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
                logger.info("Found %d pending job(s)", len(jobs))
            for job in jobs:
                _process_job_safe(db, job)
        except Exception as e:
            logger.error("Unexpected error in poll cycle: %s", e, exc_info=True)
        finally:
            db.close()

        time.sleep(settings.poll_interval_seconds)


if __name__ == "__main__":
    run_worker()
