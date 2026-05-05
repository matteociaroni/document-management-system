from fastapi import APIRouter, Depends, HTTPException, Query, Form, File, UploadFile
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional
from app.database import get_db
from app.models import User, Document, Folder, EmailAttachment
from app.schemas import DocumentUploadRequest, DocumentUploadResponse, DocumentConfirmRequest, DocumentResponse, DownloadUrlResponse, MoveRequest
from app.auth import get_current_user
from app.storage import generate_upload_url, generate_download_url, get_s3_client, get_bucket_name
from app.permissions_helper import has_permission, has_write_permission
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/documents", tags=["documents"])


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


def _get_document_or_404(db: Session, document_id: UUID, user: User, check_permission: bool = False) -> Document:
    """Fetch document by ID with optional permission check"""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if check_permission and doc.owner_id != user.id:
        has_doc_perm = has_permission(db, user.id, document_id=document_id)
        has_folder_perm = doc.folder_id and _has_access_to_folder(db, user.id, doc.folder_id)
        if not has_doc_perm and not has_folder_perm:
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
        if folder.owner_id != user.id and not has_write_permission(db, user.id, folder_id=folder_id):
            raise HTTPException(status_code=403, detail="No write access to folder")
    
    # Use only basename for the filename (in case it has path components from webkitRelativePath)
    import os
    filename = os.path.basename(file.filename) if file.filename else "file"
    
    doc = Document(name=filename, mime_type=file.content_type, folder_id=folder_id, owner_id=user.id)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    
    try:
        s3 = get_s3_client()
        bucket = get_bucket_name(user.email)
        try:
            s3.head_bucket(Bucket=bucket)
        except Exception as e:
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
        error_str = str(e)
        if '404' in error_str or 'NoSuchKey' in error_str:
            raise HTTPException(status_code=410, detail="File not found in storage")
        raise HTTPException(status_code=500, detail="Failed to retrieve file")


@router.get("", response_model=list[DocumentResponse])
def list_documents(
    folder_id: Optional[UUID] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if folder_id is not None:
        folder = db.query(Folder).filter(Folder.id == folder_id).first()
        if not folder:
            raise HTTPException(status_code=404, detail="Folder not found")

        if not _has_access_to_folder(db, user.id, folder_id):
            raise HTTPException(status_code=403, detail="Access denied")

        query = db.query(Document).filter(Document.folder_id == folder_id)
    else:
        query = db.query(Document).filter(Document.folder_id == None)
        query = query.filter(Document.owner_id == user.id)

    # Hide documents that are still sitting in the agent inbox awaiting user review
    inbox_doc_ids = db.query(EmailAttachment.document_id).filter(
        EmailAttachment.status == "in_inbox",
        EmailAttachment.document_id.isnot(None),
    )
    query = query.filter(~Document.id.in_(inbox_doc_ids))

    return query.limit(limit).offset(offset).all()


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _get_document_or_404(db, document_id, user, check_permission=True)





@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = _get_document_or_404(db, document_id, user, check_permission=False)
    
    if doc.owner_id != user.id:
        if not doc.folder_id:
            raise HTTPException(status_code=403, detail="Only owner can delete root documents")
        
        folder = db.query(Folder).filter(Folder.id == doc.folder_id).first()
        if folder.owner_id != user.id and not has_write_permission(db, user.id, folder_id=doc.folder_id):
            raise HTTPException(status_code=403, detail="No write access to folder")
    
    db.delete(doc)
    db.commit()


@router.post("/{document_id}/copy", response_model=DocumentResponse)
def copy_document(document_id: UUID, req: MoveRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = _get_document_or_404(db, document_id, user, check_permission=True)
    
    if req.new_folder_id:
        dest_folder = db.query(Folder).filter(Folder.id == req.new_folder_id).first()
        if not dest_folder:
            raise HTTPException(status_code=404, detail="Destination folder not found")
        if dest_folder.owner_id != user.id and not has_write_permission(db, user.id, folder_id=req.new_folder_id):
            raise HTTPException(status_code=403, detail="No write access to destination folder")
            
    new_doc = Document(
        name=doc.name,
        mime_type=doc.mime_type,
        size_bytes=doc.size_bytes,
        folder_id=req.new_folder_id,
        owner_id=user.id
    )
    db.add(new_doc)
    db.flush()
    
    try:
        s3 = get_s3_client()
        dest_bucket = get_bucket_name(user.email)
        src_bucket = get_bucket_name(doc.owner.email)
        
        try:
            s3.head_bucket(Bucket=dest_bucket)
        except Exception as e:
            if '404' in str(e) or 'Not Found' in str(e):
                s3.create_bucket(Bucket=dest_bucket)
            else:
                raise
                
        copy_src = f"{src_bucket}/{doc.id}"
        print(f"DEBUG documents.py CopySource: {copy_src!r}", flush=True)
        s3.copy_object(CopySource=copy_src, Bucket=dest_bucket, Key=str(new_doc.id))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to copy file in storage. It may not exist on S3. Error: " + str(e))
        
    db.commit()
    db.refresh(new_doc)
    return new_doc


@router.patch("/{document_id}/move", response_model=DocumentResponse)
def move_document(document_id: UUID, req: MoveRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = _get_document_or_404(db, document_id, user, check_permission=False)
    
    if doc.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Only owner can move this document")
        
    if req.new_folder_id:
        dest_folder = db.query(Folder).filter(Folder.id == req.new_folder_id).first()
        if not dest_folder:
            raise HTTPException(status_code=404, detail="Destination folder not found")
        if dest_folder.owner_id != user.id and not has_write_permission(db, user.id, folder_id=req.new_folder_id):
            raise HTTPException(status_code=403, detail="No write access to destination folder")
            
    doc.folder_id = req.new_folder_id
    db.commit()
    db.refresh(doc)
    return doc
