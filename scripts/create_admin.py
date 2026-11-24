"""
دروستکردن یان نوێکردنەوەی هەژماری Admin بە ئیمەیڵ (بۆ نموونە Gmail) و وشەی نهێنی.

بەکارهێنان (لە فۆڵدەری سەرەکیی پرۆژەکە، لە PowerShell یان تێرمیناڵی VS Code):
    python scripts/create_admin.py you@gmail.com
    python scripts/create_admin.py you@gmail.com --name "Miran"

وشەی نهێنی دوو جار دەپرسرێت و لە کاتی نووسیندا پیشان نادرێت.
  - ئەگەر ئەم ئیمەیڵە هەژماری نەبێت: هەژمارێکی Admin ی نوێ دروست دەکرێت.
  - ئەگەر هەبێت: دەکرێت بە Admin، چالاک دەکرێت، و وشەی نهێنییەکەی دەگۆڕدرێت.
دوای ئەوە لە وێبسایتەکە بەم ئیمەیڵ و وشەی نهێنییە بچۆ ژوورەوە.
"""
import argparse
import getpass
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

from backend.database import Base, SessionLocal, engine  # noqa: E402
from backend.models import User  # noqa: E402
from backend.schemas import EMAIL_PATTERN  # noqa: E402
from backend.security import hash_password  # noqa: E402

MIN_PASSWORD = 8


def ask_password():
    for _ in range(3):
        pw = getpass.getpass("وشەی نهێنی (لانیکەم 8 پیت): ")
        if len(pw) < MIN_PASSWORD:
            print(f"✗ وشەی نهێنی دەبێت لانیکەم {MIN_PASSWORD} پیت بێت.")
            continue
        if getpass.getpass("دووبارە بینووسەوە: ") != pw:
            print("✗ وەک یەک نین. دووبارە هەوڵ بدەوە.")
            continue
        return pw
    sys.exit("✗ وشەی نهێنی دانەنرا.")


def main():
    ap = argparse.ArgumentParser(description="دروستکردنی هەژماری Admin")
    ap.add_argument("email", help="ئیمەیڵ، بۆ نموونە you@gmail.com")
    ap.add_argument("--name", default=None, help="ناو (بنەڕەت: Admin)")
    args = ap.parse_args()

    email = args.email.strip().lower()  # وەک چوونەژوورەوە: ئیمەیڵ بە پیتی بچووک
    if not re.match(EMAIL_PATTERN, email) or len(email) > 160:
        sys.exit(f"✗ ئیمەیڵ دروست نییە: {args.email}")
    password = ask_password()

    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(name=(args.name or "Admin").strip()[:80], email=email,
                        password_hash=hash_password(password), role="admin")
            db.add(user)
            action = "دروست کرا"
        else:
            user.role = "admin"
            user.is_active = True
            user.password_hash = hash_password(password)
            if args.name:
                user.name = args.name.strip()[:80]
            action = "نوێ کرایەوە (کرا بە Admin و وشەی نهێنی گۆڕدرا)"
        db.commit()
    print(f"✓ هەژماری Admin {action}: {email}")
    print("  ئێستا لە وێبسایتەکە بەم ئیمەیڵ و وشەی نهێنییە بچۆ ژوورەوە.")


if __name__ == "__main__":
    main()
