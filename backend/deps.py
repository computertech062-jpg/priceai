"""Dependencies: بەکارهێنەری ئێستا، پشکنینی Admin، و Predictor."""
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import User
from .security import decode_token

bearer = HTTPBearer(auto_error=False)


def api_error(status_code: int, code: str, **extra) -> HTTPException:
    """هەڵەکان بە code دەگەڕێنەوە، Frontend بە کوردی یان ئینگلیزی وەریدەگێڕێت."""
    return HTTPException(status_code, detail={"code": code, **extra})


def get_predictor(request: Request):
    predictor = getattr(request.app.state, "predictor", None)
    if predictor is None:
        raise api_error(status.HTTP_503_SERVICE_UNAVAILABLE, "model_unavailable")
    return predictor


def get_price_history(request: Request):
    """مێژووی نرخ (data/price_history.csv). ئەگەر فایلەکە نوێ بووەوە، دووبارە بار دەکرێتەوە."""
    from .ml.history import DATA, PriceHistory
    mtime = DATA.stat().st_mtime if DATA.exists() else None
    cached = getattr(request.app.state, "price_history", None)
    if cached is None or cached[0] != mtime:
        cached = (mtime, PriceHistory(DATA))
        request.app.state.price_history = cached
    return cached[1]


def get_forecaster(request: Request):
    """پێشبینیی نرخ بە پێی کات. لەگەڵ نوێبوونەوەی data/price_history.csv دووبارە دروست دەبێتەوە."""
    from .ml.forecast import Forecaster
    from .ml.history import DATA
    mtime = DATA.stat().st_mtime if DATA.exists() else None
    cached = getattr(request.app.state, "forecaster", None)
    if cached is None or cached[0] != mtime:
        cached = (mtime, Forecaster(DATA))
        request.app.state.forecaster = cached
    return cached[1]


def get_optional_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer),
                      db: Session = Depends(get_db)) -> User | None:
    if not creds:
        return None
    user_id = decode_token(creds.credentials)
    if user_id is None:
        return None
    user = db.get(User, user_id)
    return user if user and user.is_active else None


def require_login(user: User | None = Depends(get_optional_user)) -> User | None:
    """ئەگەر REQUIRE_LOGIN چالاک بێت، تەنها بەکارهێنەری چووەژوورەوە سیستەمەکە بەکاردەهێنێت."""
    if settings.REQUIRE_LOGIN and user is None:
        raise api_error(status.HTTP_401_UNAUTHORIZED, "auth_required")
    return user


def get_current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer),
                     db: Session = Depends(get_db)) -> User:
    if not creds:
        raise api_error(status.HTTP_401_UNAUTHORIZED, "auth_required")
    user_id = decode_token(creds.credentials)
    user = db.get(User, user_id) if user_id is not None else None
    if not user:
        raise api_error(status.HTTP_401_UNAUTHORIZED, "session_expired")
    if not user.is_active:
        raise api_error(status.HTTP_403_FORBIDDEN, "account_disabled")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise api_error(status.HTTP_403_FORBIDDEN, "admin_only")
    return user
