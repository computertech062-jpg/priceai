from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import api_error, require_admin
from ..models import Prediction, User
from ..schemas import UserUpdate
from ..services import prediction_out, user_out

router = APIRouter(prefix="/api/admin", tags=["Admin"])


@router.get("/users")
def users(q: str = Query("", max_length=80), db: Session = Depends(get_db), _=Depends(require_admin)):
    counts = dict(db.execute(select(Prediction.user_id, func.count(Prediction.id))
                             .group_by(Prediction.user_id)).all())
    stmt = select(User).order_by(User.created_at.desc())
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(User.name.ilike(like), User.email.ilike(like)))
    return {"items": [{**user_out(u), "predictions": counts.get(u.id, 0)} for u in db.scalars(stmt).all()]}


@router.patch("/users/{user_id}")
def update_user(user_id: int, body: UserUpdate, db: Session = Depends(get_db),
                admin: User = Depends(require_admin)):
    u = db.get(User, user_id)
    if not u:
        raise api_error(status.HTTP_404_NOT_FOUND, "not_found")
    if u.id == admin.id and (body.role == "user" or body.is_active is False):
        raise api_error(status.HTTP_400_BAD_REQUEST, "cannot_change_self")
    if body.role is not None:
        u.role = body.role
    if body.is_active is not None:
        u.is_active = body.is_active
    db.commit()
    return user_out(u)


@router.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    u = db.get(User, user_id)
    if not u:
        raise api_error(status.HTTP_404_NOT_FOUND, "not_found")
    if u.id == admin.id:
        raise api_error(status.HTTP_400_BAD_REQUEST, "cannot_change_self")
    db.delete(u)
    db.commit()
    return {"ok": True}


@router.get("/predictions")
def recent_predictions(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db),
                       _=Depends(require_admin)):
    rows = db.execute(select(Prediction, User.name).join(User, User.id == Prediction.user_id)
                      .order_by(Prediction.created_at.desc()).limit(limit)).all()
    return {"items": [{**prediction_out(p), "user_name": name} for p, name in rows]}
