from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional
from app.database import get_db
from app.models import User, Document, Folder
from app.schemas import DocumentUploadRequest, DocumentUploadResponse, DocumentConfirmRequest, DocumentResponse, DownloadUrlResponse
from app.auth import get_current_user
from app.storage import generate_upload_url, generate_download_url
from app.permissions_helper import has_permission

router = APIRouter(prefix="/documents", tags=["documents"])


def _get_document_or_404(db: Session, document_id: UUID, user: User, check_permission: bool = False) -> Document:
    """Fetch document by ID with optional permission check"""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if check_permission and doc.owner_id != user.id and not has_permission(db, user.id, document_id=document_id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    return doc


@router.post("/upload-url", response_model=DocumentUploadResponse)
def get_upload_url(req: DocumentUploadRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if req.folder_id:
        folder = db.query(Folder).filter(Folder.id == req.folder_id).first()
        if not folder:
            raise HTTPException(status_code=404, detail="Folder not found")
        if folder.owner_id != user.id and not has_permission(db, user.id, folder_id=req.folder_id):
            raise HTTPException(status_code=403, detail="No access to folder")
    
    doc = Document(name=req.filename, mime_type=req.mime_type, folder_id=req.folder_id, owner_id=user.id)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    
    upload_url = generate_upload_url(str(doc.id), user.email)
    return {"document_id": doc.id, "upload_url": upload_url}


@router.post("/confirm")
def confirm_upload(req: DocumentConfirmRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == req.document_id, Document.owner_id == user.id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    doc.size_bytes = req.size_bytes
    db.commit()
    db.refresh(doc)
    return {"message": "Upload confirmed"}


@router.get("", response_model=list[DocumentResponse])
def list_documents(
    folder_id: Optional[UUID] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Document).filter(Document.owner_id == user.id)
    if folder_id:
        query = query.filter(Document.folder_id == folder_id)
    
    return query.limit(limit).offset(offset).all()


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _get_document_or_404(db, document_id, user, check_permission=True)


@router.get("/{document_id}/download-url", response_model=DownloadUrlResponse)
def get_download_url(document_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = _get_document_or_404(db, document_id, user, check_permission=True)
    download_url = generate_download_url(str(doc.id), doc.owner.email)
    return {"download_url": download_url}


@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = _get_document_or_404(db, document_id, user, check_permission=False)
    
    if doc.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Only owner can delete")
    
    db.delete(doc)
    db.commit()
