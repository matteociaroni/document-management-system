from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, History
from app.schemas import HistoryCreate, HistoryResponse
from app.auth import get_current_user

router = APIRouter(prefix="/history", tags=["history"])


@router.post("", response_model=HistoryResponse)
def add_history(req: HistoryCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    h = History(user_id=user.id, action=req.action)
    db.add(h)
    db.commit()
    db.refresh(h)
    return h


@router.get("", response_model=list[HistoryResponse])
def get_history(limit: int = Query(50, ge=1, le=100), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(History).filter(History.user_id == user.id).order_by(History.timestamp.desc()).limit(limit).all()
