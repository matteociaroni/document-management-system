from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from uuid import UUID
from app.database import get_db
from app.models import User, Document
from app.schemas import UserResponse, AdminUpdateStatusRequest, AdminUpdateRoleRequest, DomainMetricsResponse, UserRole
from app.auth import get_current_user

router = APIRouter(prefix="/admin", tags=["admin"])


def get_current_domain_admin(user: User = Depends(get_current_user)):
    if user.role != UserRole.DOMAIN_ADMIN.value:
        raise HTTPException(status_code=403, detail="Requires DOMAIN_ADMIN privileges")
    return user


def get_user_domain(email: str) -> str:
    return email.split('@')[1] if '@' in email else ""


@router.get("/users", response_model=list[UserResponse])
def get_domain_users(
    admin: User = Depends(get_current_domain_admin),
    db: Session = Depends(get_db)
):
    domain = get_user_domain(admin.email)
    users = db.query(User).filter(User.email.like(f"%@{domain}")).all()
    return users


@router.patch("/users/{user_id}/status", response_model=UserResponse)
def update_user_status(
    user_id: UUID,
    req: AdminUpdateStatusRequest,
    admin: User = Depends(get_current_domain_admin),
    db: Session = Depends(get_db)
):
    domain = get_user_domain(admin.email)
    target_user = db.query(User).filter(User.id == user_id).first()
    
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if get_user_domain(target_user.email) != domain:
        raise HTTPException(status_code=403, detail="User belongs to a different domain")
        
    if target_user.id == admin.id and not req.is_active:
        raise HTTPException(status_code=400, detail="Cannot disable your own admin account")
        
    target_user.is_active = req.is_active
    db.commit()
    db.refresh(target_user)
    return target_user


@router.patch("/users/{user_id}/role", response_model=UserResponse)
def update_user_role(
    user_id: UUID,
    req: AdminUpdateRoleRequest,
    admin: User = Depends(get_current_domain_admin),
    db: Session = Depends(get_db)
):
    domain = get_user_domain(admin.email)
    target_user = db.query(User).filter(User.id == user_id).first()
    
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if get_user_domain(target_user.email) != domain:
        raise HTTPException(status_code=403, detail="User belongs to a different domain")
        
    if target_user.id == admin.id and req.role != UserRole.DOMAIN_ADMIN.value:
        raise HTTPException(status_code=400, detail="Cannot downgrade your own admin account")
        
    target_user.role = req.role.value
    db.commit()
    db.refresh(target_user)
    return target_user


@router.get("/metrics", response_model=DomainMetricsResponse)
def get_domain_metrics(
    admin: User = Depends(get_current_domain_admin),
    db: Session = Depends(get_db)
):
    domain = get_user_domain(admin.email)
    
    domain_users_query = db.query(User.id).filter(User.email.like(f"%@{domain}"))
    
    total_users = domain_users_query.count()
    active_users = db.query(User).filter(User.email.like(f"%@{domain}"), User.is_active == True).count()
    
    docs_stats = db.query(
        func.count(Document.id),
        func.sum(Document.size_bytes)
    ).filter(Document.owner_id.in_(domain_users_query)).first()
    
    return DomainMetricsResponse(
        total_users=total_users,
        active_users=active_users,
        total_documents=docs_stats[0] or 0,
        total_storage_bytes=docs_stats[1] or 0
    )


from app.models import History
from app.schemas import HistoryResponse

@router.get("/audit", response_model=list[HistoryResponse])
def get_domain_audit(
    limit: int = Query(100, ge=1, le=500),
    admin: User = Depends(get_current_domain_admin),
    db: Session = Depends(get_db)
):
    domain = get_user_domain(admin.email)
    domain_users_query = db.query(User.id).filter(User.email.like(f"%@{domain}"))
    
    audit_logs = db.query(History).filter(
        History.user_id.in_(domain_users_query)
    ).order_by(History.timestamp.desc()).limit(limit).all()
    
    return audit_logs
