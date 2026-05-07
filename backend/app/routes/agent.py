"""Routes for the AI agent page: operation log and proposals management."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID
from app.database import get_db
from app.models import User, EmailAttachment, EmailJob, AgentOperation, Document, Folder
from app.schemas import AgentOperationResponse, ProposalResponse, ProposalMoveRequest
from app.auth import get_current_user
from app.storage import get_s3_client, get_bucket_name

router = APIRouter(prefix="/agent", tags=["agent"])


def _get_attachment_for_user(
    db: Session, attachment_id: UUID, user: User
) -> EmailAttachment:
    """Fetch an attachment belonging to the current user, or raise 404."""
    attachment = (
        db.query(EmailAttachment)
        .join(EmailJob, EmailAttachment.job_id == EmailJob.id)
        .join(
            __import__("app.models", fromlist=["EmailAccount"]).EmailAccount,
            EmailJob.email_account_id
            == __import__("app.models", fromlist=["EmailAccount"]).EmailAccount.id,
        )
        .filter(
            EmailAttachment.id == attachment_id,
            __import__("app.models", fromlist=["EmailAccount"]).EmailAccount.user_id
            == user.id,
        )
        .first()
    )
    if not attachment:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return attachment


@router.get("/operations", response_model=list[AgentOperationResponse])
def list_agent_operations(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the paginated log of agent operations for the current user, newest first."""
    return (
        db.query(AgentOperation)
        .filter(AgentOperation.user_id == user.id)
        .order_by(AgentOperation.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )


@router.get("/proposals", response_model=list[ProposalResponse])
def list_proposals(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all attachments currently sitting in inbox-email awaiting user review."""
    from app.models import EmailAccount

    rows = (
        db.query(EmailAttachment, EmailJob, Folder)
        .join(EmailJob, EmailAttachment.job_id == EmailJob.id)
        .join(EmailAccount, EmailJob.email_account_id == EmailAccount.id)
        .outerjoin(Folder, EmailAttachment.suggested_folder_id == Folder.id)
        .filter(
            EmailAccount.user_id == user.id,
            EmailAttachment.status == "in_inbox",
        )
        .order_by(EmailAttachment.created_at.desc())
        .all()
    )

    results = []
    for attachment, job, suggested_folder in rows:
        results.append(
            ProposalResponse(
                id=attachment.id,
                filename=attachment.filename,
                mime_type=attachment.mime_type,
                size_bytes=attachment.size_bytes,
                suggested_folder_id=attachment.suggested_folder_id,
                confidence=attachment.confidence,
                agent_reasoning=attachment.agent_reasoning,
                document_id=attachment.document_id,
                status=attachment.status,
                created_at=attachment.created_at,
                suggested_folder_name=suggested_folder.name if suggested_folder else None,
                sender=job.sender,
                subject=job.subject,
            )
        )
    return results


def _move_document_to_folder(
    db: Session,
    attachment: EmailAttachment,
    user: User,
    target_folder_id: Optional[UUID],
    log_description: str,
):
    """Move the document associated with an attachment to target_folder_id (None = root) and update status."""
    doc = db.query(Document).filter(Document.id == attachment.document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Associated document not found")

    folder = None
    if target_folder_id is not None:
        folder = db.query(Folder).filter(Folder.id == target_folder_id).first()
        if not folder:
            raise HTTPException(status_code=404, detail="Target folder not found")
        if folder.owner_id != user.id:
            raise HTTPException(status_code=403, detail="No access to target folder")

    doc.folder_id = target_folder_id
    attachment.status = "confirmed"

    op = AgentOperation(
        user_id=user.id,
        job_id=attachment.job_id,
        attachment_id=attachment.id,
        operation_type="auto_filed",
        description=log_description,
        details={
            "folder_id": str(target_folder_id) if target_folder_id else None,
            "folder_name": folder.name if folder else "My Drive (root)",
        },
    )
    db.add(op)
    db.commit()
    db.refresh(attachment)


@router.post("/proposals/{attachment_id}/accept", response_model=ProposalResponse)
def accept_proposal(
    attachment_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Accept the agent's suggestion: move the document to the suggested folder."""
    from app.models import EmailAccount

    attachment = (
        db.query(EmailAttachment)
        .join(EmailJob, EmailAttachment.job_id == EmailJob.id)
        .join(EmailAccount, EmailJob.email_account_id == EmailAccount.id)
        .filter(
            EmailAttachment.id == attachment_id,
            EmailAccount.user_id == user.id,
            EmailAttachment.status == "in_inbox",
        )
        .first()
    )
    if not attachment:
        raise HTTPException(status_code=404, detail="Proposal not found or already resolved")

    if not attachment.suggested_folder_id:
        raise HTTPException(
            status_code=400,
            detail="No suggested folder to accept — use /move to specify a folder",
        )

    job = db.query(EmailJob).filter(EmailJob.id == attachment.job_id).first()
    _move_document_to_folder(
        db,
        attachment,
        user,
        attachment.suggested_folder_id,
        f"User accepted proposal: '{attachment.filename}' moved to suggested folder",
    )

    folder = db.query(Folder).filter(Folder.id == attachment.suggested_folder_id).first()
    return ProposalResponse(
        id=attachment.id,
        filename=attachment.filename,
        mime_type=attachment.mime_type,
        size_bytes=attachment.size_bytes,
        suggested_folder_id=attachment.suggested_folder_id,
        confidence=attachment.confidence,
        agent_reasoning=attachment.agent_reasoning,
        document_id=attachment.document_id,
        status=attachment.status,
        created_at=attachment.created_at,
        suggested_folder_name=folder.name if folder else None,
        sender=job.sender if job else None,
        subject=job.subject if job else None,
    )


@router.post("/proposals/{attachment_id}/move", response_model=ProposalResponse)
def move_proposal(
    attachment_id: UUID,
    req: ProposalMoveRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Move the document to a user-chosen folder (different from the suggestion)."""
    from app.models import EmailAccount

    attachment = (
        db.query(EmailAttachment)
        .join(EmailJob, EmailAttachment.job_id == EmailJob.id)
        .join(EmailAccount, EmailJob.email_account_id == EmailAccount.id)
        .filter(
            EmailAttachment.id == attachment_id,
            EmailAccount.user_id == user.id,
            EmailAttachment.status == "in_inbox",
        )
        .first()
    )
    if not attachment:
        raise HTTPException(status_code=404, detail="Proposal not found or already resolved")

    job = db.query(EmailJob).filter(EmailJob.id == attachment.job_id).first()
    _move_document_to_folder(
        db,
        attachment,
        user,
        req.folder_id,
        f"User moved '{attachment.filename}' to a different folder than suggested",
    )

    folder = (
        db.query(Folder).filter(Folder.id == req.folder_id).first()
        if req.folder_id is not None
        else None
    )
    return ProposalResponse(
        id=attachment.id,
        filename=attachment.filename,
        mime_type=attachment.mime_type,
        size_bytes=attachment.size_bytes,
        suggested_folder_id=attachment.suggested_folder_id,
        confidence=attachment.confidence,
        agent_reasoning=attachment.agent_reasoning,
        document_id=attachment.document_id,
        status=attachment.status,
        created_at=attachment.created_at,
        suggested_folder_name=folder.name if folder else None,
        sender=job.sender if job else None,
        subject=job.subject if job else None,
    )


@router.post("/proposals/{attachment_id}/reject", response_model=ProposalResponse)
def reject_proposal(
    attachment_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reject the proposal: file stays in inbox-email, status set to 'rejected'."""
    from app.models import EmailAccount

    attachment = (
        db.query(EmailAttachment)
        .join(EmailJob, EmailAttachment.job_id == EmailJob.id)
        .join(EmailAccount, EmailJob.email_account_id == EmailAccount.id)
        .filter(
            EmailAttachment.id == attachment_id,
            EmailAccount.user_id == user.id,
            EmailAttachment.status == "in_inbox",
        )
        .first()
    )
    if not attachment:
        raise HTTPException(status_code=404, detail="Proposal not found or already resolved")

    attachment.status = "rejected"

    op = AgentOperation(
        user_id=user.id,
        job_id=attachment.job_id,
        attachment_id=attachment.id,
        operation_type="sent_to_inbox",
        description=f"User rejected proposal for '{attachment.filename}' — file remains in inbox-email",
    )
    db.add(op)
    db.commit()
    db.refresh(attachment)

    job = db.query(EmailJob).filter(EmailJob.id == attachment.job_id).first()
    folder = (
        db.query(Folder).filter(Folder.id == attachment.suggested_folder_id).first()
        if attachment.suggested_folder_id
        else None
    )
    return ProposalResponse(
        id=attachment.id,
        filename=attachment.filename,
        mime_type=attachment.mime_type,
        size_bytes=attachment.size_bytes,
        suggested_folder_id=attachment.suggested_folder_id,
        confidence=attachment.confidence,
        agent_reasoning=attachment.agent_reasoning,
        document_id=attachment.document_id,
        status=attachment.status,
        created_at=attachment.created_at,
        suggested_folder_name=folder.name if folder else None,
        sender=job.sender if job else None,
        subject=job.subject if job else None,
    )
