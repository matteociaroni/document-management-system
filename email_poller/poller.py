"""
IMAP Poller — main loop.

Runs every 60 seconds. On each cycle it:
  1. Queries the DB for accounts due for polling (via scheduler).
  2. For each account, connects via IMAP and fetches new emails with attachments.
  3. Saves each raw email as .eml in object storage.
  4. Creates an EmailJob record in the DB (status='pending') for the agent worker.
  5. Logs each received email in agent_operations.
  6. Updates last_uid and last_synced_at.

Errors on individual accounts are caught and logged without stopping the cycle.
"""

import logging
import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from database import SessionLocal
from models import AgentOperation, EmailAccount, EmailJob
import eml_storage
import imap_client
import scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("email_poller")

POLL_INTERVAL_SECONDS = 60


def _process_account(db: Session, account: EmailAccount) -> None:
    """Fetch new emails for one account and create EmailJob records."""
    conn = None
    try:
        conn = imap_client.connect(account)
        new_emails = imap_client.fetch_new_emails(conn, account.last_uid or 0)

        max_uid = account.last_uid or 0

        for raw_email in new_emails:
            # Check for duplicate job (same account + uid) — UNIQUE constraint handles it,
            # but we check first to avoid a log noise on IntegrityError
            existing = (
                db.query(EmailJob)
                .filter(
                    EmailJob.email_account_id == account.id,
                    EmailJob.message_uid == raw_email.uid,
                )
                .first()
            )
            if existing:
                logger.debug(
                    "Skipping already-seen UID %d for account %s",
                    raw_email.uid, account.email_address,
                )
                max_uid = max(max_uid, raw_email.uid)
                continue

            # Create the EmailJob record first so we have its id for the storage key
            job = EmailJob(
                email_account_id=account.id,
                message_uid=raw_email.uid,
                subject=raw_email.subject,
                sender=raw_email.sender,
                received_at=raw_email.received_at,
                status="pending",
            )
            db.add(job)
            db.flush()  # get job.id without committing

            # Store the raw .eml in object storage
            storage_key = eml_storage.store_eml(str(job.id), raw_email.raw_bytes)
            job.eml_storage_key = storage_key

            # Log the operation for the frontend timeline
            # Resolve user_id through the relationship chain
            op = AgentOperation(
                user_id=account.user_id,
                job_id=job.id,
                operation_type="email_received",
                description=f"Nuova email ricevuta da {raw_email.sender}: \"{raw_email.subject}\"",
                details={
                    "uid": raw_email.uid,
                    "sender": raw_email.sender,
                    "subject": raw_email.subject,
                    "eml_key": storage_key,
                },
            )
            db.add(op)

            max_uid = max(max_uid, raw_email.uid)
            logger.info(
                "Queued job for UID %d (%s) from %s",
                raw_email.uid, raw_email.subject, account.email_address,
            )

        # Update account state
        account.last_uid = max_uid
        account.last_synced_at = datetime.now(timezone.utc)
        db.commit()

    except Exception as e:
        db.rollback()
        logger.error(
            "Error polling account %s: %s", account.email_address, e, exc_info=True
        )
        # Still update last_synced_at to avoid hammering a broken account every 60s
        try:
            account.last_synced_at = datetime.now(timezone.utc)
            db.commit()
        except Exception:
            db.rollback()
    finally:
        if conn:
            try:
                conn.logout()
            except Exception:
                pass


def poll_cycle(db: Session) -> None:
    """Run one full polling cycle across all due accounts."""
    due_accounts = scheduler.get_accounts_to_poll(db)

    if not due_accounts:
        logger.debug("No accounts due for polling this cycle.")
        return

    logger.info("Polling %d account(s) this cycle.", len(due_accounts))
    for account in due_accounts:
        _process_account(db, account)


def run_poller() -> None:
    """Entry point: blocking loop that runs poll_cycle every POLL_INTERVAL_SECONDS."""
    logger.info("Email poller started. Interval: %ds", POLL_INTERVAL_SECONDS)
    logger.debug("Debug enabled")

    while True:
        logger.debug("Before session")
        db: Session = SessionLocal()
        logger.debug("After session")
        try:
            logger.debug("Before poll cycle")
            poll_cycle(db)
            logger.debug("After poll cycle")
        except Exception as e:
            logger.error("Unexpected error in poll cycle: %s", e, exc_info=True)
        finally:
            logger.debug("Before closing")
            db.close()
            logger.debug("After closing")

        logger.debug("Before sleep")
        time.sleep(POLL_INTERVAL_SECONDS)
        logger.debug("After sleep")

if __name__ == "__main__":
    run_poller()
