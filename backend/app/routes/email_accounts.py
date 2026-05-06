"""CRUD routes for email account management."""

import imaplib
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from uuid import UUID
from app.database import get_db
from app.models import User, EmailAccount
from app.schemas import (
    EmailAccountCreate,
    EmailAccountUpdate,
    EmailAccountResponse,
    EmailAccountTestResponse,
)
from app.auth import get_current_user
from app.crypto import encrypt_credentials, decrypt_credentials

router = APIRouter(prefix="/email-accounts", tags=["email-accounts"])


@router.post("", response_model=EmailAccountResponse)
def create_email_account(
    req: EmailAccountCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new email account. Credentials are encrypted before storage."""
    if req.auth_type not in ("app_password", "oauth2"):
        raise HTTPException(status_code=400, detail="auth_type must be 'app_password' or 'oauth2'")

    if req.auth_type == "oauth2" and not req.oauth_provider:
        raise HTTPException(status_code=400, detail="oauth_provider is required for OAuth2 accounts")

    encrypted = encrypt_credentials(req.credentials)

    account = EmailAccount(
        user_id=user.id,
        email_address=req.email_address,
        imap_host=req.imap_host,
        imap_port=req.imap_port,
        use_ssl=req.use_ssl,
        auth_type=req.auth_type,
        encrypted_credentials=encrypted,
        oauth_provider=req.oauth_provider,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@router.get("", response_model=list[EmailAccountResponse])
def list_email_accounts(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all email accounts for the current user. Credentials are never returned."""
    return (
        db.query(EmailAccount)
        .filter(EmailAccount.user_id == user.id)
        .order_by(EmailAccount.created_at.desc())
        .all()
    )


@router.get("/{account_id}", response_model=EmailAccountResponse)
def get_email_account(
    account_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific email account by ID."""
    account = db.query(EmailAccount).filter(
        EmailAccount.id == account_id,
        EmailAccount.user_id == user.id,
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Email account not found")
    return account


@router.patch("/{account_id}", response_model=EmailAccountResponse)
def update_email_account(
    account_id: UUID,
    req: EmailAccountUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update an email account configuration. If credentials are provided, they are re-encrypted."""
    account = db.query(EmailAccount).filter(
        EmailAccount.id == account_id,
        EmailAccount.user_id == user.id,
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Email account not found")

    if req.imap_host is not None:
        account.imap_host = req.imap_host
    if req.imap_port is not None:
        account.imap_port = req.imap_port
    if req.use_ssl is not None:
        account.use_ssl = req.use_ssl
    if req.is_active is not None:
        # When re-activating, reset last_synced_at so the poller
        # re-initialises last_uid to the current max UID on the server,
        # skipping emails that arrived while the account was paused.
        if req.is_active and not account.is_active:
            account.last_synced_at = None
        account.is_active = req.is_active
    if req.credentials is not None:
        account.encrypted_credentials = encrypt_credentials(req.credentials)

    db.commit()
    db.refresh(account)
    return account


@router.delete("/{account_id}", status_code=204)
def delete_email_account(
    account_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete an email account. Only the owner can delete."""
    account = db.query(EmailAccount).filter(
        EmailAccount.id == account_id,
        EmailAccount.user_id == user.id,
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Email account not found")

    db.delete(account)
    db.commit()


@router.post("/{account_id}/test", response_model=EmailAccountTestResponse)
def test_email_account(
    account_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Test IMAP connection with the saved credentials."""
    account = db.query(EmailAccount).filter(
        EmailAccount.id == account_id,
        EmailAccount.user_id == user.id,
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Email account not found")

    try:
        password = decrypt_credentials(account.encrypted_credentials)

        if account.use_ssl:
            conn = imaplib.IMAP4_SSL(account.imap_host, account.imap_port)
        else:
            conn = imaplib.IMAP4(account.imap_host, account.imap_port)

        if account.auth_type == "oauth2":
            # XOAUTH2 authentication
            import base64
            auth_string = f"user={account.email_address}\x01auth=Bearer {password}\x01\x01"
            conn.authenticate("XOAUTH2", lambda x: auth_string.encode())
        else:
            conn.login(account.email_address, password)

        conn.logout()
        return EmailAccountTestResponse(success=True, message="Connection successful")

    except imaplib.IMAP4.error as e:
        return EmailAccountTestResponse(success=False, message=f"IMAP error: {str(e)}")
    except Exception as e:
        return EmailAccountTestResponse(success=False, message=f"Connection failed: {str(e)}")


@router.post("/sync", status_code=202)
def trigger_sync(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Trigger an immediate sync for all active email accounts of the current user.
    Sets last_synced_at to NULL so the poller picks them up on the next cycle."""
    accounts = (
        db.query(EmailAccount)
        .filter(EmailAccount.user_id == user.id, EmailAccount.is_active == True)
        .all()
    )
    if not accounts:
        raise HTTPException(status_code=404, detail="No active email accounts found")

    for account in accounts:
        account.last_synced_at = None

    db.commit()
    return {"message": f"Sync triggered for {len(accounts)} account(s)"}
