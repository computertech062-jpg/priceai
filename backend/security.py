"""
ئاسایش: hash کردنی وشەی نهێنی (PBKDF2-SHA256) و JWT.

وشەی نهێنی هەرگیز بە ڕوونی پاشەکەوت ناکرێت. تەنها hash ـەکەی، لەگەڵ salt ێکی
هەڕەمەکی بۆ هەر بەکارهێنەرێک.
"""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from .config import settings

ITERATIONS = 240_000
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt, digest = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        calc = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations))
        return hmac.compare_digest(calc.hex(), digest)
    except (ValueError, TypeError):
        return False


def create_token(user_id: int, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "role": role, "iat": now,
               "exp": now + timedelta(hours=settings.TOKEN_HOURS)}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str):
    """دەگەڕێنێتەوە: user_id یان None ئەگەر token هەڵە یان بەسەرچوو بێت."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
