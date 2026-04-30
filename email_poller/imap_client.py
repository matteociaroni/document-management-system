"""
Unified IMAP client supporting both App Password and OAuth2 (XOAUTH2) authentication.

Uses imaplib from stdlib plus imapclient for higher-level UID operations.
"""

import base64
import email
import imaplib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from crypto import decrypt_credentials
from models import EmailAccount

logger = logging.getLogger(__name__)


@dataclass
class RawEmail:
    """A fetched email message with its metadata."""
    uid: int
    subject: str
    sender: str
    received_at: datetime | None
    raw_bytes: bytes
    has_attachments: bool


def _build_xoauth2_string(email_address: str, access_token: str) -> bytes:
    """Build the XOAUTH2 SASL token string."""
    auth_string = f"user={email_address}\x01auth=Bearer {access_token}\x01\x01"
    return base64.b64encode(auth_string.encode())


def _refresh_oauth2_token(account: EmailAccount) -> str:
    """
    Exchange the stored refresh_token for a fresh access_token.
    Supports Gmail and Outlook (Microsoft).
    """
    import urllib.request
    import urllib.parse
    import json
    from config import settings

    refresh_token = decrypt_credentials(account.encrypted_credentials)

    if account.oauth_provider == "gmail":
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
    elif account.oauth_provider == "outlook":
        token_url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
        data = {
            "client_id": settings.microsoft_client_id,
            "client_secret": settings.microsoft_client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
            "scope": "https://outlook.office.com/IMAP.AccessAsUser.All offline_access",
        }
    else:
        raise ValueError(f"Unknown OAuth provider: {account.oauth_provider}")

    req = urllib.request.Request(
        token_url,
        data=urllib.parse.urlencode(data).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = json.loads(resp.read())

    access_token = body.get("access_token")
    if not access_token:
        raise RuntimeError(f"OAuth token refresh failed: {body}")
    return access_token


def connect(account: EmailAccount) -> imaplib.IMAP4_SSL | imaplib.IMAP4:
    """
    Open and authenticate an IMAP connection for the given account.

    Handles both 'app_password' and 'oauth2' auth types transparently.
    Returns an authenticated imaplib connection with INBOX selected.
    """
    logger.info("Connecting to IMAP: %s:%d for %s", account.imap_host, account.imap_port, account.email_address)

    if account.use_ssl:
        conn = imaplib.IMAP4_SSL(account.imap_host, account.imap_port)
    else:
        conn = imaplib.IMAP4(account.imap_host, account.imap_port)

    if account.auth_type == "app_password":
        password = decrypt_credentials(account.encrypted_credentials)
        conn.login(account.email_address, password)

    elif account.auth_type == "oauth2":
        access_token = _refresh_oauth2_token(account)
        xoauth2 = _build_xoauth2_string(account.email_address, access_token)
        conn.authenticate("XOAUTH2", lambda _: xoauth2)

    else:
        raise ValueError(f"Unsupported auth_type: {account.auth_type}")

    conn.select("INBOX")
    logger.info("IMAP authenticated for %s", account.email_address)
    return conn


def _message_has_attachments(msg: email.message.Message) -> bool:
    """Return True if the parsed email contains at least one non-inline attachment."""
    for part in msg.walk():
        content_disposition = part.get_content_disposition()
        if content_disposition == "attachment":
            return True
        # Some clients use 'inline' with a filename — treat those as attachments too
        if content_disposition == "inline" and part.get_filename():
            return True
    return False


def get_max_uid(conn: imaplib.IMAP4_SSL | imaplib.IMAP4) -> int:
    """Return the highest UID currently in the INBOX, or 0 if empty."""
    _, data = conn.uid("SEARCH", None, "ALL")
    if not data or not data[0]:
        return 0
    uids = data[0].split()
    if not uids:
        return 0
    return int(uids[-1])


def fetch_new_emails(conn: imaplib.IMAP4_SSL | imaplib.IMAP4, last_uid: int) -> list[RawEmail]:
    """
    Fetch all messages with UID > last_uid that contain attachments.

    Args:
        conn: An authenticated IMAP connection with INBOX selected.
        last_uid: The highest UID already processed (0 = start of mailbox).

    Returns:
        List of RawEmail for messages with attachments, ordered by UID ascending.
    """
    search_criterion = f"UID {last_uid + 1}:*"
    _, data = conn.uid("SEARCH", None, search_criterion)  # type: ignore[arg-type]

    if not data or not data[0]:
        return []

    uids = data[0].split()
    if not uids:
        return []

    results: list[RawEmail] = []

    for uid_bytes in uids:
        uid = int(uid_bytes)
        if uid <= last_uid:
            # IMAP returns * (highest) even if nothing newer exists
            continue

        try:
            _, msg_data = conn.uid("FETCH", str(uid), "(RFC822)")  # type: ignore[arg-type]
            if not msg_data or msg_data[0] is None:
                continue

            raw_bytes: bytes = msg_data[0][1]  # type: ignore[index]
            msg = email.message_from_bytes(raw_bytes)

            has_attachments = _message_has_attachments(msg)
            if not has_attachments:
                # Skip messages without attachments — nothing for the agent to do
                continue

            # Extract metadata
            subject = email.header.decode_header(msg.get("Subject", ""))[0]
            subject_str = (
                subject[0].decode(subject[1] or "utf-8") if isinstance(subject[0], bytes) else subject[0]
            )

            sender = msg.get("From", "")
            date_str = msg.get("Date", "")
            try:
                from email.utils import parsedate_to_datetime
                received_at = parsedate_to_datetime(date_str)
            except Exception:
                received_at = None

            results.append(
                RawEmail(
                    uid=uid,
                    subject=subject_str,
                    sender=sender,
                    received_at=received_at,
                    raw_bytes=raw_bytes,
                    has_attachments=True,
                )
            )

        except Exception as e:
            logger.warning("Failed to fetch UID %d: %s", uid, e)
            continue

    logger.info("Fetched %d new email(s) with attachments (last_uid=%d)", len(results), last_uid)
    return results
