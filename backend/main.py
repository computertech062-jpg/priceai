"""
PriceAI — دەستپێکی Backend.

ڕاکردن (لە فۆڵدەری سەرەکیی پرۆژەکە):
    uvicorn backend.main:app --reload
پاشان بکەرەوە:  http://127.0.0.1:8000        (وێبسایت)
                 http://127.0.0.1:8000/docs   (بەڵگەنامەی API، Swagger)
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from .config import settings
from .database import Base, SessionLocal, engine
from .models import User
from .routers import admin, auth, dashboard, history, phones, predict
from .security import hash_password

log = logging.getLogger("priceai")


def ensure_admin():
    """ئەگەر ADMIN_EMAIL و ADMIN_PASSWORD دانرابن، هەژماری Admin دروست دەکات."""
    if not (settings.ADMIN_EMAIL and settings.ADMIN_PASSWORD):
        return
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == settings.ADMIN_EMAIL))
        if user is None:
            db.add(User(name="Admin", email=settings.ADMIN_EMAIL,
                        password_hash=hash_password(settings.ADMIN_PASSWORD), role="admin"))
            db.commit()
            log.info("Admin account created: %s", settings.ADMIN_EMAIL)
        elif user.role != "admin":
            user.role = "admin"
            db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    ensure_admin()
    try:
        from .ml.predictor import Predictor
        app.state.predictor = Predictor(data_path=settings.DATA_PATH)
        log.info("Model loaded: %s", app.state.predictor.model_name)
    except FileNotFoundError as e:
        app.state.predictor = None
        log.warning("%s", e)
    if settings.SECRET_KEY_IS_TEMPORARY:
        log.warning("SECRET_KEY is not set; using a temporary key (users are logged out on restart).")
    yield


app = FastAPI(
    title="PriceAI API",
    description="AI-Based Mobile Phone Price Prediction System",
    version="1.0.0",
    lifespan=lifespan,
)

if settings.CORS_ORIGINS:
    app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS,
                       allow_methods=["*"], allow_headers=["*"])

for r in (auth.router, phones.router, predict.router, history.router, dashboard.router, admin.router):
    app.include_router(r)


@app.get("/api/config", tags=["System"])
def public_config():
    """ڕێکخستنە گشتییەکان بۆ Frontend (پێش چوونەژوورەوە)."""
    return {"require_login": settings.REQUIRE_LOGIN, "languages": ["ku", "ar", "en"]}


@app.get("/api/health", tags=["System"])
def health():
    p = getattr(app.state, "predictor", None)
    return {"status": "ok", "model_loaded": p is not None, "model": p.model_name if p else None}


# Frontend (دەبێت لە کۆتاییدا بێت، دوای هەموو API ـەکان)
app.mount("/", StaticFiles(directory=settings.FRONTEND_DIR, html=True), name="frontend")
