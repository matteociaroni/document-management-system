"""
Scheduler for IMAP polling.

Strategy:
- Active users  (last_active_at < 2 hours ago): poll every 1 hour
- Inactive users (last_active_at >= 2 hours ago): poll every 24 hours
- An account is eligible when: now - last_synced_at >= required_interval
  OR last_synced_at IS NULL (forced sync requested)
"""

from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from app.models import EmailAccount, User

ACTIVE_INTERVAL = timedelta(hours=1)
INACTIVE_INTERVAL = timedelta(hours=24)
ACTIVE_THRESHOLD = timedelta(hours=2)


def get_accounts_to_poll(db: Session) -> list[EmailAccount]:
    """
    Return the list of active email accounts that are due for a poll right now.
    """
    now = datetime.now(timezone.utc)

    accounts: list[EmailAccount] = (
        db.query(EmailAccount)
        .filter(EmailAccount.is_active == True)
        .all()
    )

    due = []
    for account in accounts:
        user: User = account.user

        # Determine if user is "active" based on last_active_at
        last_active = user.last_active_at
        if last_active and last_active.tzinfo is None:
            last_active = last_active.replace(tzinfo=timezone.utc)

        is_active_user = last_active is not None and (now - last_active) < ACTIVE_THRESHOLD
        required_interval = ACTIVE_INTERVAL if is_active_user else INACTIVE_INTERVAL

        # NULL last_synced_at means a forced sync was requested (or first ever sync)
        if account.last_synced_at is None:
            due.append(account)
            continue

        last_synced = account.last_synced_at
        if last_synced.tzinfo is None:
            last_synced = last_synced.replace(tzinfo=timezone.utc)

        if (now - last_synced) >= required_interval:
            due.append(account)

    return due
