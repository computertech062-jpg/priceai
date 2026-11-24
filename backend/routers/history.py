from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import api_error, get_current_user
from ..models import Prediction, User
from ..services import prediction_out

router = APIRouter(prefix="/api/history", tags=["History"])


@router.get("")
def list_history(q: str = Query("", max_length=80), verdict: str = Query("", max_length=20),
                 page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
                 db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(Prediction).where(Prediction.user_id == user.id)
    if q.strip():
        stmt = stmt.where(Prediction.phone_name.ilike(f"%{q.strip()}%"))
    if verdict in ("cheap", "fair", "expensive"):
        stmt = stmt.where(Prediction.verdict == verdict)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(Prediction.created_at.desc(), Prediction.id.desc())
                      .offset((page - 1) * size).limit(size)).all()
    return {"items": [prediction_out(p) for p in rows], "total": total, "page": page, "size": size}


@router.get("/{prediction_id}")
def get_one(prediction_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    p = db.get(Prediction, prediction_id)
    if not p or p.user_id != user.id:
        raise api_error(status.HTTP_404_NOT_FOUND, "not_found")
    return prediction_out(p, full=True)


@router.delete("/{prediction_id}")
def delete_one(prediction_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    p = db.get(Prediction, prediction_id)
    if not p or p.user_id != user.id:
        raise api_error(status.HTTP_404_NOT_FOUND, "not_found")
    db.delete(p)
    db.commit()
    return {"ok": True}


@router.delete("")
def clear(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    res = db.execute(delete(Prediction).where(Prediction.user_id == user.id))
    db.commit()
    return {"ok": True, "deleted": res.rowcount}
