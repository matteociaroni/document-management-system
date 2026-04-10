from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional
from app.database import get_db
from app.models import User, Folder
from app.schemas import FolderCreate, FolderResponse, MoveRequest
from app.auth import get_current_user
from app.permissions_helper import has_permission, has_write_permission

router = APIRouter(prefix="/folders", tags=["folders"])


def _get_folder_or_404(db: Session, folder_id: UUID, user: User, check_permission: bool = False) -> Folder:
    """Fetch folder by ID with optional permission check"""
    folder = db.query(Folder).filter(Folder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    if check_permission and folder.owner_id != user.id and not has_permission(db, user.id, folder_id=folder_id):
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
    query = db.query(Folder).filter(Folder.owner_id == user.id)
    if parent_id is not None:
        query = query.filter(Folder.parent_id == parent_id)
    else:
        query = query.filter(Folder.parent_id == None)
    return query.limit(limit).offset(offset).all()


@router.get("/{folder_id}", response_model=FolderResponse)
def get_folder(folder_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _get_folder_or_404(db, folder_id, user, check_permission=True)


@router.delete("/{folder_id}", status_code=204)
def delete_folder(folder_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    folder = _get_folder_or_404(db, folder_id, user, check_permission=False)
    
    if folder.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Only owner can delete")
    
    db.delete(folder)
    db.commit()


@router.patch("/{folder_id}/move", response_model=FolderResponse)
def move_folder(folder_id: UUID, req: MoveRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    folder = _get_folder_or_404(db, folder_id, user, check_permission=False)
    
    if folder.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Only owner can move this folder")
        
    if req.new_folder_id:
        dest_folder = _get_folder_or_404(db, req.new_folder_id, user, check_permission=False)
        if dest_folder.owner_id != user.id and not has_write_permission(db, user.id, folder_id=req.new_folder_id):
            raise HTTPException(status_code=403, detail="No write access to destination folder")
            
    folder.parent_id = req.new_folder_id
    db.commit()
    db.refresh(folder)
    return folder
