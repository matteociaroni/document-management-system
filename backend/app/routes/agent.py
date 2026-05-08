"""Routes for the AI agent page: operation log and proposals management.

Proposals can originate from two sources:
  - 'email'         — agent processed an inbound email attachment
  - 'manual_upload' — user uploaded a file via the "Upload with AI" button

Authorization for proposals is derived from Document.owner_id so that both
sources are handled uniformly.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID
from app.database import get_db
from app.models import User, AgentFile, EmailJob, AgentOperation, Document, Folder
from app.schemas import AgentOperationResponse, ProposalResponse, ProposalMoveRequest
from app.auth import get_current_user
from app.storage import get_s3_client, get_bucket_name

router = APIRouter(prefix="/agent", tags=["agent"])


def _get_user_agent_file(
    db: Session, agent_file_id: UUID, user: User, expected_status: Optional[str] = None
) -> AgentFile:
    """Fetch an agent file owned by the current user (via Document.owner_id),
    works for both 'email' and 'manual_upload' sources. Raises 404 if not
    found or not accessible."""
    agent_file = (
        db.query(AgentFile)
        .join(Document, AgentFile.document_id == Document.id)
        .filter(
            AgentFile.id == agent_file_id,
            Document.owner_id == user.id,
        )
        .first()
    )
    if not agent_file:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if expected_status and agent_file.status != expected_status:
        raise HTTPException(status_code=404, detail="Proposal not found or already resolved")
    return agent_file


def _build_proposal_response(
    db: Session, agent_file: AgentFile
) -> ProposalResponse:
    """Hydrate a ProposalResponse from an AgentFile, joining optional
    metadata (folder, email job)."""
    folder = (
        db.query(Folder).filter(Folder.id == agent_file.suggested_folder_id).first()
        if agent_file.suggested_folder_id
        else None
    )
    job = (
        db.query(EmailJob).filter(EmailJob.id == agent_file.job_id).first()
        if agent_file.job_id
        else None
    )
    return ProposalResponse(
        id=agent_file.id,
        filename=agent_file.filename,
        mime_type=agent_file.mime_type,
        size_bytes=agent_file.size_bytes,
        suggested_folder_id=agent_file.suggested_folder_id,
        confidence=agent_file.confidence,
        agent_reasoning=agent_file.agent_reasoning,
        document_id=agent_file.document_id,
        status=agent_file.status,
        created_at=agent_file.created_at,
        suggested_folder_name=folder.name if folder else None,
        sender=job.sender if job else None,
        subject=job.subject if job else None,
        source=agent_file.source,
    )


@router.get("/operations", response_model=list[AgentOperationResponse])
def list_agent_operations(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the paginated log of agent operations for the current user, newest first."""
    operations = (
        db.query(AgentOperation)
        .filter(AgentOperation.user_id == user.id)
        .order_by(AgentOperation.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )

    all_folders = db.query(Folder.id, Folder.parent_id).filter(Folder.owner_id == user.id).all()
    parent_map = {str(f.id): str(f.parent_id) if f.parent_id else None for f in all_folders}

    result = []
    for op in operations:
        op_dict = AgentOperationResponse.model_validate(op).model_dump()
        affected_folders = set()
        if op.details and "folder_id" in op.details and op.details["folder_id"]:
            current_id = op.details["folder_id"]
            while current_id:
                affected_folders.add(current_id)
                current_id = parent_map.get(current_id)
        
        op_dict["affected_folder_ids"] = list(affected_folders)
        result.append(op_dict)
        
    return result


@router.get("/proposals", response_model=list[ProposalResponse])
def list_proposals(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all agent files currently sitting in the inbox awaiting user
    review. Includes both email-derived and manual-upload-derived items."""
    rows = (
        db.query(AgentFile, Document, Folder, EmailJob)
        .join(Document, AgentFile.document_id == Document.id)
        .outerjoin(Folder, AgentFile.suggested_folder_id == Folder.id)
        .outerjoin(EmailJob, AgentFile.job_id == EmailJob.id)
        .filter(
            Document.owner_id == user.id,
            AgentFile.status == "in_inbox",
        )
        .order_by(AgentFile.created_at.desc())
        .all()
    )

    return [
        ProposalResponse(
            id=agent_file.id,
            filename=agent_file.filename,
            mime_type=agent_file.mime_type,
            size_bytes=agent_file.size_bytes,
            suggested_folder_id=agent_file.suggested_folder_id,
            confidence=agent_file.confidence,
            agent_reasoning=agent_file.agent_reasoning,
            document_id=agent_file.document_id,
            status=agent_file.status,
            created_at=agent_file.created_at,
            suggested_folder_name=folder.name if folder else None,
            sender=job.sender if job else None,
            subject=job.subject if job else None,
            source=agent_file.source,
        )
        for agent_file, _doc, folder, job in rows
    ]


def _move_document_to_folder(
    db: Session,
    agent_file: AgentFile,
    user: User,
    target_folder_id: Optional[UUID],
    log_description: str,
):
    """Move the document associated with an agent_file to target_folder_id (None = root) and update status."""
    doc = db.query(Document).filter(Document.id == agent_file.document_id).first()
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
    agent_file.status = "confirmed"

    op = AgentOperation(
        user_id=user.id,
        job_id=agent_file.job_id,
        agent_file_id=agent_file.id,
        operation_type="auto_filed",
        description=log_description,
        details={
            "folder_id": str(target_folder_id) if target_folder_id else None,
            "folder_name": folder.name if folder else "My Drive (root)",
        },
    )
    db.add(op)
    db.commit()
    db.refresh(agent_file)


@router.post("/proposals/{proposal_id}/accept", response_model=ProposalResponse)
def accept_proposal(
    proposal_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Accept the agent's suggestion: move the document to the suggested folder."""
    agent_file = _get_user_agent_file(db, proposal_id, user, expected_status="in_inbox")

    if not agent_file.suggested_folder_id:
        raise HTTPException(
            status_code=400,
            detail="No suggested folder to accept — use /move to specify a folder",
        )

    _move_document_to_folder(
        db,
        agent_file,
        user,
        agent_file.suggested_folder_id,
        f"User accepted proposal: '{agent_file.filename}' moved to suggested folder",
    )
    return _build_proposal_response(db, agent_file)


@router.post("/proposals/{proposal_id}/move", response_model=ProposalResponse)
def move_proposal(
    proposal_id: UUID,
    req: ProposalMoveRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Move the document to a user-chosen folder (different from the suggestion)."""
    agent_file = _get_user_agent_file(db, proposal_id, user, expected_status="in_inbox")

    _move_document_to_folder(
        db,
        agent_file,
        user,
        req.folder_id,
        f"User moved '{agent_file.filename}' to a different folder than suggested",
    )
    return _build_proposal_response(db, agent_file)


@router.post("/proposals/{proposal_id}/reject", response_model=ProposalResponse)
def reject_proposal(
    proposal_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reject the proposal: file stays in the inbox, status set to 'rejected'."""
    agent_file = _get_user_agent_file(db, proposal_id, user, expected_status="in_inbox")

    agent_file.status = "rejected"
    op = AgentOperation(
        user_id=user.id,
        job_id=agent_file.job_id,
        agent_file_id=agent_file.id,
        operation_type="sent_to_inbox",
        description=f"User rejected proposal for '{agent_file.filename}' — file remains in inbox",
    )
    db.add(op)
    db.commit()
    db.refresh(agent_file)
    return _build_proposal_response(db, agent_file)
