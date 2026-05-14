from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional
from app.database import get_db
from app.models import User, Folder, Document, AgentFile, AgentOperation
from app.schemas import FolderCreate, FolderResponse, MoveRequest
from app.auth import get_current_user
from app.permissions_helper import has_permission, has_write_permission
from app.storage import get_s3_client, get_tenant_folder
from app.config import settings

router = APIRouter(prefix="/folders", tags=["folders"])


def _has_access_to_folder(db: Session, user_id: UUID, folder_id: UUID) -> bool:
    """Check if user has access to a folder via ownership or explicit permission.
    Also returns True if user owns any ancestor folder."""
    folder = db.query(Folder).filter(Folder.id == folder_id).first()
    if not folder:
        return False
    
    # User owns this folder
    if folder.owner_id == user_id:
        return True
    
    # User has explicit permission
    if has_permission(db, user_id, folder_id=folder_id):
        return True
    
    # Check if user owns any ancestor folder
    current = folder
    while current.parent_id:
        parent = db.query(Folder).filter(Folder.id == current.parent_id).first()
        if not parent:
            break
        if parent.owner_id == user_id:
            return True
        current = parent
    
    return False


def _get_folder_or_404(db: Session, folder_id: UUID, user: User, check_permission: bool = False) -> Folder:
    """Fetch folder by ID with optional permission check"""
    folder = db.query(Folder).filter(Folder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    if check_permission and not _has_access_to_folder(db, user.id, folder_id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    return folder


@router.post("", response_model=FolderResponse)
def create_folder(req: FolderCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if req.parent_id:
        parent = db.query(Folder).filter(Folder.id == req.parent_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent folder not found")
        if parent.owner_id != user.id and not has_permission(db, user.id, folder_id=parent.id):
            raise HTTPException(status_code=403, detail="No access to parent folder")
    
    folder = Folder(name=req.name, parent_id=req.parent_id, owner_id=user.id)
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return folder


@router.get("", response_model=list[FolderResponse])
def list_folders(
    parent_id: Optional[UUID] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if parent_id is not None:
        parent_folder = db.query(Folder).filter(Folder.id == parent_id).first()
        if not parent_folder:
            raise HTTPException(status_code=404, detail="Parent folder not found")
        
        if not _has_access_to_folder(db, user.id, parent_id):
            raise HTTPException(status_code=403, detail="Access denied")
        
        query = db.query(Folder).filter(Folder.parent_id == parent_id, Folder.id != parent_id)
    else:
        query = db.query(Folder).filter(Folder.owner_id == user.id)
        query = query.filter(Folder.parent_id == None)
    
    return query.limit(limit).offset(offset).all()


@router.get("/{folder_id}", response_model=FolderResponse)
def get_folder(folder_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _get_folder_or_404(db, folder_id, user, check_permission=True)


def _collect_documents_recursive(db: Session, folder_id: UUID) -> list[Document]:
    """Return every Document under this folder and any descendant subfolder."""
    docs = list(db.query(Document).filter(Document.folder_id == folder_id).all())
    subfolders = db.query(Folder).filter(Folder.parent_id == folder_id).all()
    for sub in subfolders:
        docs.extend(_collect_documents_recursive(db, sub.id))
    return docs


@router.delete("/{folder_id}", status_code=204)
def delete_folder(folder_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    folder = _get_folder_or_404(db, folder_id, user, check_permission=False)

    if folder.owner_id != user.id:
        if not folder.parent_id:
            raise HTTPException(status_code=403, detail="Only owner can delete root folders")

        parent = db.query(Folder).filter(Folder.id == folder.parent_id).first()
        if parent.owner_id != user.id and not has_write_permission(db, user.id, folder_id=folder.parent_id):
            raise HTTPException(status_code=403, detail="No write access to parent folder")

    docs = _collect_documents_recursive(db, folder_id)

    # agent_files.document_id is ON DELETE SET NULL, so the DB cascade would
    # leave orphan pending entries the worker keeps retrying. Detach the
    # agent_operations FK then remove the agent_files explicitly.
    if docs:
        doc_ids = [d.id for d in docs]
        linked_agent_files = (
            db.query(AgentFile).filter(AgentFile.document_id.in_(doc_ids)).all()
        )
        for af in linked_agent_files:
            db.query(AgentOperation).filter(
                AgentOperation.agent_file_id == af.id
            ).update({"agent_file_id": None})
            db.delete(af)

    # Snapshot what we need *before* the cascade nukes the rows.
    opensearch_targets = [(d.owner_id, d.id) for d in docs]
    bucket_targets = [(get_tenant_folder(d.owner.email), str(d.id)) for d in docs]

    # Remove bucket objects before commit. If any non-idempotent error happens
    # we abort so the folder stays visible — leaving orphan files in the
    # bucket is exactly what we're fixing.
    try:
        s3 = get_s3_client()
        bucket = settings.gcp_bucket_name
        for tenant_folder, doc_id_str in bucket_targets:
            try:
                s3.delete_object(Bucket=bucket, Key=f"{tenant_folder}/{doc_id_str}")
            except Exception as e:
                error_str = str(e)
                if '404' not in error_str and 'NoSuchKey' not in error_str:
                    raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete folder contents from storage: {e}")

    db.delete(folder)
    db.commit()

    # OpenSearch tenant index cleanup (best effort).
    from app.routes.search import delete_from_index
    for owner_id, doc_id in opensearch_targets:
        delete_from_index(owner_id, doc_id)


def _copy_folder_recursive(db, s3, src_folder_id, dest_parent_id, user):
    src_folder = db.query(Folder).filter(Folder.id == src_folder_id).first()
    new_folder = Folder(name=src_folder.name, parent_id=dest_parent_id, owner_id=user.id)
    db.add(new_folder)
    db.flush()
    
    bucket = settings.gcp_bucket_name
    dest_folder = get_tenant_folder(user.email)
    
    try:
        s3.head_bucket(Bucket=bucket)
    except Exception as e:
        if '404' in str(e) or 'Not Found' in str(e) or 'NoSuchBucket' in str(e):
            s3.create_bucket(Bucket=bucket)
        else:
            raise
            
    docs = db.query(Document).filter(Document.folder_id == src_folder_id).all()
    for doc in docs:
        src_folder = get_tenant_folder(doc.owner.email)
        new_doc = Document(
            name=doc.name,
            mime_type=doc.mime_type,
            size_bytes=doc.size_bytes,
            folder_id=new_folder.id,
            owner_id=user.id
        )
        db.add(new_doc)
        db.flush()
        copy_src = f"{bucket}/{src_folder}/{doc.id}"
        print(f"DEBUG folders.py CopySource: {copy_src!r}", flush=True)
        try:
            s3.copy_object(CopySource=copy_src, Bucket=bucket, Key=f"{dest_folder}/{str(new_doc.id)}")
        except Exception as e:
            print(f"WARNING: Skipping S3 copy for missing object {copy_src}. Error: {e}", flush=True)
        
    subfolders = db.query(Folder).filter(Folder.parent_id == src_folder_id).all()
    for sub in subfolders:
        _copy_folder_recursive(db, s3, sub.id, new_folder.id, user)
        
    return new_folder


@router.post("/{folder_id}/copy", response_model=FolderResponse)
def copy_folder(folder_id: UUID, req: MoveRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    folder = _get_folder_or_404(db, folder_id, user, check_permission=True)
    
    if req.new_folder_id:
        dest_folder = _get_folder_or_404(db, req.new_folder_id, user, check_permission=False)
        if dest_folder.owner_id != user.id and not has_write_permission(db, user.id, folder_id=req.new_folder_id):
            raise HTTPException(status_code=403, detail="No write access to destination folder")
            
    try:
        s3 = get_s3_client()
        new_folder = _copy_folder_recursive(db, s3, folder.id, req.new_folder_id, user)
        db.commit()
        db.refresh(new_folder)
        return new_folder
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to copy folder contents: " + str(e))


@router.patch("/{folder_id}/move", response_model=FolderResponse)
def move_folder(folder_id: UUID, req: MoveRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    folder = _get_folder_or_404(db, folder_id, user, check_permission=False)
    
    if folder.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Only owner can move this folder")
    
    if req.new_folder_id:
        if req.new_folder_id == folder_id:
            raise HTTPException(status_code=400, detail="Cannot move folder into itself")
        
        dest_folder = _get_folder_or_404(db, req.new_folder_id, user, check_permission=False)
        if dest_folder.owner_id != user.id and not has_write_permission(db, user.id, folder_id=req.new_folder_id):
            raise HTTPException(status_code=403, detail="No write access to destination folder")
            
    folder.parent_id = req.new_folder_id
    db.commit()
    db.refresh(folder)
    return folder
