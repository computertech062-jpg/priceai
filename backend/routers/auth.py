from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import api_error, get_current_user
from ..models import User
from ..schemas import LoginIn, RegisterIn
from ..security import create_token, hash_password, verify_password
from ..services import user_out

router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == body.email)):
        raise api_error(status.HTTP_409_CONFLICT, "email_taken")
    # یەکەم بەکارهێنەر دەبێتە Admin
    is_first = (db.scalar(select(func.count(User.id))) or 0) == 0
    user = User(name=body.name, email=body.email, password_hash=hash_password(body.password),
                role="admin" if is_first else "user")
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"token": create_token(user.id, user.role), "user": user_out(user)}


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email))
    if not user or not verify_password(body.password, user.password_hash):
        raise api_error(status.HTTP_401_UNAUTHORIZED, "bad_credentials")
    if not user.is_active:
        raise api_error(status.HTTP_403_FORBIDDEN, "account_disabled")
    return {"token": create_token(user.id, user.role), "user": user_out(user)}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return user_out(user)
