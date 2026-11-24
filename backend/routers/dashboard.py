from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, get_predictor, require_login
from ..models import Prediction, User
from ..services import dashboard as build_dashboard

router = APIRouter(prefix="/api", tags=["Dashboard"])


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(get_current_user),
              predictor=Depends(get_predictor)):
    preds = db.scalars(select(Prediction).where(Prediction.user_id == user.id)).all()
    admin = None
    if user.role == "admin":
        admin = {
            "users": db.scalar(select(func.count(User.id))) or 0,
            "active_users": db.scalar(select(func.count(User.id)).where(User.is_active.is_(True))) or 0,
            "predictions": db.scalar(select(func.count(Prediction.id))) or 0,
        }
    return build_dashboard(preds, predictor.model_info(), admin=admin)


@router.get("/model", dependencies=[Depends(require_login)])
def model_info(predictor=Depends(get_predictor)):
    """ئەدای مۆدێل: بەراوردی ئەلگۆریتمەکان، گرافەکان، گرینگیی تایبەتمەندییەکان."""
    return predictor.model_info()
