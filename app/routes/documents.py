from fastapi import APIRouter, Depends, HTTPException, Query, Form, File, UploadFile
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional
from app.database import get_db
from app.models import User, Document, Folder
from app.schemas import DocumentUploadRequest, DocumentUploadResponse, DocumentConfirmRequest, DocumentResponse, DownloadUrlResponse, MoveRequest
from app.auth import get_current_user
from app.storage import generate_upload_url, generate_download_url, get_s3_client, get_bucket_name
from app.permissions_helper import has_permission
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/documents", tags=["documents"])


def _get_document_or_404(db: Session, document_id: UUID, user: User, check_permission: bool = False) -> Document:
    """Fetch document by ID with optional permission check"""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if check_permission and doc.owner_id != user.id and not has_permission(db, user.id, document_id=document_id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    return doc

@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    folder_id: Optional[UUID] = Form(None),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if folder_id:
        folder = db.query(Folder).filter(Folder.id == folder_id).first()
        if not folder:
            raise HTTPException(status_code=404, detail="Folder not found")
        if folder.owner_id != user.id and not has_permission(db, user.id, folder_id=folder_id):
            raise HTTPException(status_code=403, detail="No access to folder")
            
    doc = Document(name=file.filename, mime_type=file.content_type, folder_id=folder_id, owner_id=user.id)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    
    try:
        s3 = get_s3_client()
        bucket = get_bucket_name(user.email)
        try:
            s3.head_bucket(Bucket=bucket)
        except Exception as e:
            # SeaweedFS returns 404 on head_bucket for non-existent buckets
            if '404' in str(e):
                s3.create_bucket(Bucket=bucket)
            else:
                raise
            
        upload_url = generate_upload_url(str(doc.id), user.email, file.content_type or "application/octet-stream")
    except Exception as e:
        db.delete(doc)
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))
        
    return DocumentUploadResponse(document_id=doc.id, upload_url=upload_url)


@router.post("/{document_id}/confirm", response_model=DocumentResponse)
def confirm_document_upload(
    document_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Confirm document upload after file has been uploaded to S3"""
    doc = _get_document_or_404(db, document_id, user, check_permission=False)
    
    if doc.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Only owner can confirm upload")
    
    try:
        s3 = get_s3_client()
        bucket = get_bucket_name(user.email)
        obj = s3.head_object(Bucket=bucket, Key=str(doc.id))
        doc.size_bytes = obj['ContentLength']
        db.commit()
        db.refresh(doc)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    return doc



@router.get("/{document_id}/download")
def download_document(document_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = _get_document_or_404(db, document_id, user, check_permission=True)
    try:
        s3 = get_s3_client()
        bucket = get_bucket_name(doc.owner.email)
        obj = s3.get_object(Bucket=bucket, Key=str(doc.id))
        
        def iterfile():
            for chunk in obj['Body'].iter_chunks():
                if chunk:
                    yield chunk
                    
        return StreamingResponse(
            iterfile(),
            media_type=doc.mime_type or "application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename=\"{doc.name}\""}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=list[DocumentResponse])
def list_documents(
    folder_id: Optional[UUID] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Document).filter(Document.owner_id == user.id)
    if folder_id is not None:
        query = query.filter(Document.folder_id == folder_id)
    else:
        query = query.filter(Document.folder_id == None)
    
    return query.limit(limit).offset(offset).all()


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _get_document_or_404(db, document_id, user, check_permission=True)





@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = _get_document_or_404(db, document_id, user, check_permission=False)
    
    if doc.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Only owner can delete")
    
    db.delete(doc)
    db.commit()


@router.patch("/{document_id}/move", response_model=DocumentResponse)
def move_document(document_id: UUID, req: MoveRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = _get_document_or_404(db, document_id, user, check_permission=False)
    
    # Must own the document to move it (or have EDITOR permissions, but sticking to owner for simplicity unless specified)
    if doc.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Only owner can move this document")
        
    # Check permission for the destination folder if it exists
    if req.new_folder_id:
        dest_folder = db.query(Folder).filter(Folder.id == req.new_folder_id).first()
        if not dest_folder:
            raise HTTPException(status_code=404, detail="Destination folder not found")
        if dest_folder.owner_id != user.id and not has_permission(db, user.id, folder_id=req.new_folder_id):
            raise HTTPException(status_code=403, detail="No access to destination folder")
            
    doc.folder_id = req.new_folder_id
    db.commit()
    db.refresh(doc)
    return doc
