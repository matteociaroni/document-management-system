from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from app.database import get_db
from app.models import User, Permission, Folder, Document
from app.schemas import PermissionCreate, PermissionResponse, PermissionDetailResponse, ShareByEmailRequest
from app.auth import get_current_user

router = APIRouter(prefix="/permissions", tags=["permissions"])


def _validate_target(folder_id: UUID = None, document_id: UUID = None) -> None:
    """Validate that exactly one of folder_id or document_id is provided"""
    if not folder_id and not document_id:
        raise HTTPException(status_code=400, detail="Either folder_id or document_id required")
    if folder_id and document_id:
        raise HTTPException(status_code=400, detail="Only one of folder_id or document_id allowed")


def _validate_access_level(access_level: str) -> None:
    """Validate access level is VIEWER or EDITOR"""
    if access_level not in ["VIEWER", "EDITOR"]:
        raise HTTPException(status_code=400, detail="Invalid access level")


def _verify_resource_ownership(db: Session, user_id: UUID, folder_id: UUID = None, document_id: UUID = None) -> None:
    """Verify user owns the folder or document. Raises 404 if not found, 403 if not owned"""
    if folder_id:
        folder = db.query(Folder).filter(Folder.id == folder_id).first()
        if not folder:
            raise HTTPException(status_code=404, detail="Folder not found")
        if folder.owner_id != user_id:
            raise HTTPException(status_code=403, detail="Cannot share folder you don't own")
    else:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        if doc.owner_id != user_id:
            raise HTTPException(status_code=403, detail="Cannot share document you don't own")


@router.post("", response_model=PermissionResponse)
def create_permission(req: PermissionCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _validate_target(folder_id=req.folder_id, document_id=req.document_id)
    _verify_resource_ownership(db, user.id, folder_id=req.folder_id, document_id=req.document_id)
    _validate_access_level(req.access_level)
    
    perm = Permission(
        user_id=req.user_id,
        folder_id=req.folder_id,
        document_id=req.document_id,
        access_level=req.access_level
    )
    db.add(perm)
    db.commit()
    db.refresh(perm)
    return perm


@router.post("/share", response_model=PermissionResponse)
def share_by_email(req: ShareByEmailRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _validate_target(folder_id=req.folder_id, document_id=req.document_id)
    _verify_resource_ownership(db, user.id, folder_id=req.folder_id, document_id=req.document_id)
    _validate_access_level(req.access_level)
        
    target_user = db.query(User).filter(User.email == req.email).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")
        
    user_domain = user.email.split("@")[1] if "@" in user.email else ""
    target_domain = target_user.email.split("@")[1] if "@" in target_user.email else ""
    
    if user_domain != target_domain:
        raise HTTPException(status_code=403, detail="Users must belong to the same domain")
        
    if target_user.id == user.id:
        raise HTTPException(status_code=400, detail="Cannot share with yourself")
        
    existing = db.query(Permission).filter(
        Permission.user_id == target_user.id,
        Permission.folder_id == req.folder_id,
        Permission.document_id == req.document_id
    ).first()
    
    if existing:
        existing.access_level = req.access_level
        perm = existing
    else:
        perm = Permission(
            user_id=target_user.id,
            folder_id=req.folder_id,
            document_id=req.document_id,
            access_level=req.access_level
        )
        db.add(perm)
        
    db.commit()
    db.refresh(perm)
    return perm


@router.get("", response_model=list[PermissionResponse])
def list_permissions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Permission).filter(Permission.user_id == user.id).all()


@router.get("/resource/{resource_id}", response_model=list[PermissionDetailResponse])
def list_resource_permissions(
    resource_id: str,
    folder_id: UUID = None,
    document_id: UUID = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all permissions for a specific folder or document owned by user"""
    _validate_target(folder_id=folder_id, document_id=document_id)
    _verify_resource_ownership(db, user.id, folder_id=folder_id, document_id=document_id)
    
    query = db.query(Permission)
    if folder_id:
        query = query.filter(Permission.folder_id == folder_id)
    else:
        query = query.filter(Permission.document_id == document_id)
    
    return query.all()


@router.delete("/{permission_id}", status_code=204)
def delete_permission(permission_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    perm = db.query(Permission).filter(Permission.id == permission_id).first()
    if not perm:
        raise HTTPException(status_code=404, detail="Permission not found")
    
    # Only the owner of the shared resource can revoke
    _verify_resource_ownership(db, user.id, folder_id=perm.folder_id, document_id=perm.document_id)
    
    db.delete(perm)
    db.commit()
