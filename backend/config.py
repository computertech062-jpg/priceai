"""ڕێکخستنەکان. هەموویان لە Environment Variables یان فایلی .env دەخوێنرێنەوە."""
import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

try:  # python-dotenv ئارەزوومەندانەیە
    from dotenv import load_dotenv  # type: ignore
    load_dotenv(ROOT / ".env")
except Exception:
    pass


class Settings:
    APP_NAME = "PriceAI"
    # بنکەی زانیاری: بنەڕەت SQLite. بۆ PostgreSQL:
    #   DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/priceai
    DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{ROOT / 'priceai.db'}")
    SECRET_KEY = os.getenv("SECRET_KEY") or ""
    TOKEN_HOURS = int(os.getenv("TOKEN_HOURS", "168"))  # 7 ڕۆژ
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "").strip().lower()
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
    # چوونەژوورەوە پێویستە بۆ بەکارهێنانی سیستەمەکە (گەڕان، پێشبینی، بەراوردکردن).
    # بۆ ڕێگەدان بە میوان (بەبێ هەژمار): REQUIRE_LOGIN=0
    REQUIRE_LOGIN = os.getenv("REQUIRE_LOGIN", "1").strip().lower() not in ("0", "false", "no", "off")
    CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
    DATA_PATH = os.getenv("DATA_PATH") or None
    FRONTEND_DIR = ROOT / "frontend"


settings = Settings()

if not settings.SECRET_KEY:
    # بۆ گەشەپێدان کلیلێکی کاتی دروست دەکرێت. لە Production دا SECRET_KEY دابنێ،
    # ئەگەرنا دوای هەر Restart ێک هەموو بەکارهێنەران دەبێت دووبارە بچنە ژوورەوە.
    settings.SECRET_KEY = secrets.token_urlsafe(48)
    settings.SECRET_KEY_IS_TEMPORARY = True
else:
    settings.SECRET_KEY_IS_TEMPORARY = False
