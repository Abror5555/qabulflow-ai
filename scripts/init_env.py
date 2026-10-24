"""`.env.example` asosida `.env` yaratadi va DJANGO_SECRET_KEY'ni tasodifiy qiymat bilan to'ldiradi.

    python scripts/init_env.py           # .env bo'lmasa yaratadi
    python scripts/init_env.py --force   # mavjud .env ustidan yozadi

Tashqi kalitlar (AI, STT, Telegram) bo'sh qoladi — demo rejimi ularsiz ishlaydi.
"""

from __future__ import annotations

import argparse
import re
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    target = ROOT / ".env"
    if target.exists() and not args.force:
        print(".env allaqachon mavjud — o'zgartirilmadi (--force bilan qayta yaratish mumkin).")
        return 0
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    key = secrets.token_urlsafe(50)
    text, n = re.subn(r"^DJANGO_SECRET_KEY=.*$", f"DJANGO_SECRET_KEY={key}", text, count=1, flags=re.MULTILINE)
    if n != 1:
        print("DJANGO_SECRET_KEY qatori .env.example ichida topilmadi.", file=sys.stderr)
        return 1
    target.write_text(text, encoding="utf-8")
    print(f".env yaratildi: {target} (DJANGO_SECRET_KEY tasodifiy yaratildi)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
