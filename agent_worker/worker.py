"""
Agent Worker — main loop.

Polls the DB every POLL_INTERVAL seconds and processes two distinct queues:

  1. EmailJob records with status='pending' — produced by the email_poller.
     For each job: download the .eml, extract attachments, file them.

  2. AgentFile records with source='manual_upload' and status='pending' —
     produced by the backend's POST /documents/upload-ai endpoint or the
     direct-upload /confirm endpoint.

Pipeline applied to every file (regardless of needs_classification):
    1. Tika  — extract text from the file bytes.
    2. OpenSearch — index the extracted text (per-tenant index).
    3. LLM (filing agent) — only when needs_classification=True; decides
       auto_filed vs in_inbox based on the confidence threshold.

Files with needs_classification=False end up in status='indexed' after the
pipeline runs; they never see the LLM.
"""

import hashlib
import logging
import time
from datetime import datetime, timezone
from urllib.parse import urlparse
from uuid import UUID

from opensearchpy import OpenSearch, NotFoundError as OSNotFoundError
from sqlalchemy.orm import Session

from config import settings
from agent import run_filing_agent
from database import SessionLocal
from eml_parser import extract_text_preview, parse_email
from models import AgentOperation, Document, EmailAccount, AgentFile, EmailJob, User
from storage import ensure_bucket, get_bucket_name, get_s3_client, load_document, load_eml, EML_BUCKET
from text_extractor import extract_text_with_tika, TEXT_PREVIEW_CHARS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("agent_worker")

# ── OpenSearch helpers ──────────────────────────────────────────────────────

OPENSEARCH_INDEX_MAPPING = {
    "mappings": {
        "properties": {
            "document_id": {"type": "keyword"},
            "owner_id":    {"type": "keyword"},
            "folder_id":   {"type": "keyword"},
            "filename": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword"}},
            },
            "mime_type":   {"type": "keyword"},
            "text":        {"type": "text", "analyzer": "standard"},
            "created_at":  {"type": "date"},
        }
    }
}

# Set of index names already confirmed to exist (avoids repeated HEAD calls).
_existing_indices: set[str] = set()


def _get_opensearch_client() -> OpenSearch:
    """Create and return an OpenSearch client from settings."""
    parsed = urlparse(settings.opensearch_url)
    return OpenSearch(
        hosts=[{"host": parsed.hostname, "port": parsed.port or 9200}],
        use_ssl=False,
        verify_certs=False,
    )


def _get_index_name(owner_id) -> str:
    """Per-tenant index name: documents_<uuid_without_hyphens>."""
    return f"documents_{str(owner_id).replace('-', '')}"


def _ensure_index(client: OpenSearch, index_name: str) -> None:
    """Create the tenant index with its mapping if it doesn't already exist."""
    if index_name in _existing_indices:
        return
    if not client.indices.exists(index=index_name):
        client.indices.create(index=index_name, body=OPENSEARCH_INDEX_MAPPING)
        logger.info("Created OpenSearch index '%s'", index_name)
    _existing_indices.add(index_name)


def _index_in_opensearch(
    client: OpenSearch,
    *,
    document_id,
    owner_id,
    folder_id,
    filename: str,
    mime_type: str | None,
    text: str | None,
) -> None:
    """Pipeline step 2: send extracted text to OpenSearch for full-text search.

    Uses per-tenant indexing — each user gets their own index.  The document
    ID is used as the OpenSearch document id so re-indexing the same doc is an
    idempotent upsert.
    """
    index_name = _get_index_name(owner_id)
    _ensure_index(client, index_name)

    body = {
        "document_id": str(document_id),
        "owner_id": str(owner_id),
        "folder_id": str(folder_id) if folder_id else None,
        "filename": filename,
        "mime_type": mime_type,
        "text": text,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    client.index(index=index_name, id=str(document_id), body=body)
    logger.info(
        "Indexed document %s ('%s', %s chars) in %s",
        document_id, filename, len(text) if text else 0, index_name,
    )


# ── Existing helpers ────────────────────────────────────────────────────────

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
    agent_file_id: UUID | None,
    op_type: str,
    description: str,
    details: dict | None = None,
) -> None:
    op = AgentOperation(
        user_id=user_id,
        job_id=job_id,
        agent_file_id=agent_file_id,
        operation_type=op_type,
        description=description,
        details=details,
    )
    db.add(op)


def _process_job(db: Session, job: EmailJob, os_client: OpenSearch) -> None:
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

    # Upload attachments to SeaweedFS and create Document + AgentFile records
    s3 = get_s3_client()
    bucket = get_bucket_name(user.email)
    ensure_bucket(s3, bucket)

    records: list[tuple] = []  # (ParsedAttachment, AgentFile, Document)

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

        agent_file = AgentFile(
            job_id=job.id,
            filename=att.filename,
            mime_type=att.mime_type,
            size_bytes=att.size_bytes,
            content_hash=content_hash,
            document_id=doc.id,
            status="pending",
            needs_classification=True,
        )
        db.add(agent_file)
        db.flush()

        _log_op(
            db,
            user_id=user.id,
            job_id=job.id,
            agent_file_id=agent_file.id,
            op_type="attachment_extracted",
            description=f"Allegato estratto: '{att.filename}'",
            details={"mime_type": att.mime_type, "size_bytes": att.size_bytes},
        )
        records.append((att, agent_file, doc))

    db.commit()
    logger.info("Uploaded %d attachment(s) for job %s", len(records), job.id)

    # Pipeline step 2: index every attachment in OpenSearch (full text).
    for att, agent_file, doc in records:
        try:
            _index_in_opensearch(
                os_client,
                document_id=doc.id,
                owner_id=user.id,
                folder_id=doc.folder_id,
                filename=att.filename,
                mime_type=att.mime_type,
                text=att.full_text,
            )
        except Exception as e:
            logger.warning("OpenSearch indexing failed for doc %s: %s", doc.id, e)

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

    for att, agent_file, doc in records:
        decision = decisions_by_filename.get(att.filename)

        if not decision:
            agent_file.status = "in_inbox"
            _log_op(
                db,
                user_id=user.id,
                job_id=job.id,
                agent_file_id=agent_file.id,
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

        agent_file.suggested_folder_id = folder_uuid
        agent_file.confidence = decision.confidence
        agent_file.agent_reasoning = decision.reasoning

        if folder_uuid and decision.confidence >= settings.auto_file_threshold:
            agent_file.status = "auto_filed"
            agent_file.auto_filed = True
            doc.folder_id = folder_uuid
            _log_op(
                db,
                user_id=user.id,
                job_id=job.id,
                agent_file_id=agent_file.id,
                op_type="auto_filed",
                description=(
                    f"Archiviato automaticamente '{att.filename}' "
                    f"(confidence: {decision.confidence:.0%})"
                ),
                details={"folder_id": str(folder_uuid), "confidence": decision.confidence},
            )
        else:
            agent_file.status = "in_inbox"
            _log_op(
                db,
                user_id=user.id,
                job_id=job.id,
                agent_file_id=agent_file.id,
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


def _process_job_safe(db: Session, job: EmailJob, os_client: OpenSearch) -> None:
    """Wrap _process_job with error handling that marks the job as failed."""
    try:
        job.status = "processing"
        db.commit()
        _process_job(db, job, os_client)
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


def _get_pending_manual_uploads(db: Session) -> list[AgentFile]:
    """Pick up every pending manual upload, regardless of needs_classification.

    Both flag-on (Upload-AI) and flag-off (direct upload) files share the
    Tika+OpenSearch pipeline; only the LLM step is conditional.
    """
    return (
        db.query(AgentFile)
        .filter(
            AgentFile.source == "manual_upload",
            AgentFile.status == "pending",
        )
        .order_by(AgentFile.created_at.asc())
        .limit(10)
        .all()
    )


def _process_manual_upload(db: Session, agent_file: AgentFile, os_client: OpenSearch) -> None:
    """Run the unified pipeline for a user-uploaded document.

    Flag-off files (direct upload) stop after the OpenSearch step and end up
    in status='indexed'. Flag-on files (Upload-AI) continue through the
    filing agent for classification, ending in 'auto_filed' or 'in_inbox'.
    """
    logger.info(
        "Processing manual upload %s ('%s', needs_classification=%s)",
        agent_file.id, agent_file.filename, agent_file.needs_classification,
    )

    # Guard against orphaned records (document deleted while AgentFile was
    # still pending).  Mark as failed so the worker stops retrying.
    if not agent_file.document_id:
        logger.warning(
            "AgentFile %s has no document_id (orphaned) — marking as failed",
            agent_file.id,
        )
        agent_file.status = "failed"
        db.commit()
        return

    doc: Document = (
        db.query(Document).filter(Document.id == agent_file.document_id).first()
    )
    if not doc:
        logger.warning(
            "AgentFile %s references missing document %s — marking as failed",
            agent_file.id, agent_file.document_id,
        )
        agent_file.status = "failed"
        db.commit()
        return

    user: User = db.query(User).filter(User.id == doc.owner_id).first()
    if not user:
        raise ValueError(f"Document {doc.id} owner not found")

    # Step 1 (Tika): pull bytes from the tenant bucket and extract text.
    bucket = get_bucket_name(user.email)
    content = load_document(bucket, str(doc.id))
    full_text = extract_text_with_tika(content)
    text_preview = full_text[:TEXT_PREVIEW_CHARS] if full_text else None

    # Step 2 (OpenSearch): index full text in tenant index.
    try:
        _index_in_opensearch(
            os_client,
            document_id=doc.id,
            owner_id=user.id,
            folder_id=doc.folder_id,
            filename=agent_file.filename,
            mime_type=agent_file.mime_type,
            text=full_text,
        )
    except Exception as e:
        logger.warning("OpenSearch indexing failed for doc %s: %s", doc.id, e)

    # Step 3 (LLM): only when classification is requested. Direct uploads
    # stop here — the file is already in the user's chosen folder.
    if not agent_file.needs_classification:
        agent_file.status = "indexed"
        db.commit()
        logger.info("Manual upload %s indexed (no classification needed)", agent_file.id)
        return

    result = run_filing_agent(
        user_id=str(user.id),
        context_title=agent_file.filename,
        context_source="(manual upload)",
        context_description=None,
        attachments=[{
            "filename": agent_file.filename,
            "mime_type": agent_file.mime_type or "application/octet-stream",
            "size_bytes": agent_file.size_bytes or len(content),
            "text_preview": text_preview,
        }],
    )

    decision = next(
        (d for d in result.decisions if d.filename == agent_file.filename),
        None,
    )

    if not decision:
        agent_file.status = "in_inbox"
        _log_op(
            db,
            user_id=user.id,
            job_id=None,
            agent_file_id=agent_file.id,
            op_type="sent_to_inbox",
            description=f"'{agent_file.filename}' inviato in inbox (nessuna decisione dall'agente)",
        )
        db.commit()
        return

    folder_uuid = None
    if decision.folder_id:
        try:
            folder_uuid = UUID(decision.folder_id)
        except ValueError:
            logger.warning("Invalid folder_id from agent: %s", decision.folder_id)

    agent_file.suggested_folder_id = folder_uuid
    agent_file.confidence = decision.confidence
    agent_file.agent_reasoning = decision.reasoning

    if folder_uuid and decision.confidence >= settings.auto_file_threshold:
        agent_file.status = "auto_filed"
        agent_file.auto_filed = True
        doc.folder_id = folder_uuid
        _log_op(
            db,
            user_id=user.id,
            job_id=None,
            agent_file_id=agent_file.id,
            op_type="auto_filed",
            description=(
                f"Archiviato automaticamente '{agent_file.filename}' "
                f"(confidence: {decision.confidence:.0%})"
            ),
            details={"folder_id": str(folder_uuid), "confidence": decision.confidence},
        )
    else:
        agent_file.status = "in_inbox"
        _log_op(
            db,
            user_id=user.id,
            job_id=None,
            agent_file_id=agent_file.id,
            op_type="sent_to_inbox",
            description=(
                f"'{agent_file.filename}' inviato in inbox per revisione "
                f"(confidence: {decision.confidence:.0%})"
            ),
            details={
                "folder_id": str(folder_uuid) if folder_uuid else None,
                "confidence": decision.confidence,
            },
        )

    db.commit()


def _process_manual_upload_safe(db: Session, agent_file: AgentFile, os_client: OpenSearch) -> None:
    """Wrap _process_manual_upload so a failure on one item never stops the loop."""
    try:
        _process_manual_upload(db, agent_file, os_client)
    except Exception as e:
        db.rollback()
        logger.error("Manual upload %s failed: %s", agent_file.id, e, exc_info=True)
        try:
            # Refresh the agent_file after rollback before mutating it.
            agent_file = (
                db.query(AgentFile)
                .filter(AgentFile.id == agent_file.id)
                .first()
            )
            if agent_file is not None:
                agent_file.status = "failed"
                agent_file.agent_reasoning = (
                    "Elaborazione fallita: il file non ha potuto essere processato. "
                    "Riprova il caricamento oppure contatta l'assistenza."
                )
                # Safely resolve owner_id — document may have been deleted.
                owner_id = None
                if agent_file.document_id:
                    owner_id = (
                        db.query(Document.owner_id)
                        .filter(Document.id == agent_file.document_id)
                        .scalar()
                    )
                if owner_id:
                    db.add(AgentOperation(
                        user_id=owner_id,
                        job_id=None,
                        agent_file_id=agent_file.id,
                        operation_type="error",
                        description=f"Elaborazione fallita per '{agent_file.filename}': {e}",
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

    # Create OpenSearch client
    os_client = _get_opensearch_client()
    logger.info("OpenSearch client connected to %s", settings.opensearch_url)

    while True:
        db: Session = SessionLocal()
        try:
            jobs = _get_pending_jobs(db)
            if jobs:
                logger.info("Found %d pending email job(s)", len(jobs))
            for job in jobs:
                _process_job_safe(db, job, os_client)

            manual_uploads = _get_pending_manual_uploads(db)
            if manual_uploads:
                logger.info("Found %d pending manual upload(s)", len(manual_uploads))
            for agent_file in manual_uploads:
                _process_manual_upload_safe(db, agent_file, os_client)
        except Exception as e:
            logger.error("Unexpected error in poll cycle: %s", e, exc_info=True)
        finally:
            db.close()

        time.sleep(settings.poll_interval_seconds)


if __name__ == "__main__":
    run_worker()
