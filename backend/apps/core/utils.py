from __future__ import annotations

import re
import zoneinfo
from datetime import date, datetime, time, timedelta

from django.utils import timezone

PHONE_RE = re.compile(r"\+?\d[\d\s\-()]{7,18}\d")


def normalize_phone(raw: str | None) -> str:
    """Telefon raqamini +998XXXXXXXXX ko'rinishiga keltiradi (O'zbekiston uchun).

    Noto'g'ri bo'lsa bo'sh satr qaytaradi.
    """
    if not raw:
        return ""
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 9:
        digits = "998" + digits
    if len(digits) == 12 and digits.startswith("998"):
        return "+" + digits
    if 10 <= len(digits) <= 15 and raw.strip().startswith("+"):
        return "+" + digits
    return ""


def extract_phone(text: str) -> str:
    match = PHONE_RE.search(text or "")
    return normalize_phone(match.group(0)) if match else ""


def mask_phone(phone: str | None) -> str:
    if not phone:
        return ""
    if len(phone) < 7:
        return "***"
    return phone[:4] + "*" * (len(phone) - 6) + phone[-2:]


def org_tz(organization) -> zoneinfo.ZoneInfo:
    try:
        return zoneinfo.ZoneInfo(organization.timezone)
    except Exception:  # noqa: BLE001
        return zoneinfo.ZoneInfo("Asia/Tashkent")


def local_day_bounds(day: date, tz: zoneinfo.ZoneInfo) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=tz)
    end = start + timedelta(days=1)
    return start, end


def to_local(dt: datetime, tz: zoneinfo.ZoneInfo) -> datetime:
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.utc)
    return dt.astimezone(tz)


def parse_local_datetime(value: str, tz: zoneinfo.ZoneInfo) -> datetime:
    """'2026-10-25T10:00' yoki ISO formatini tashkilot zonasidagi aware datetime'ga aylantiradi."""
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    return dt


def parse_date_param(value: str | None, name: str = "sana") -> date | None:
    from apps.core.exceptions import BusinessError

    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise BusinessError("invalid_date", f"{name} formati YYYY-MM-DD bo'lishi kerak.", status_code=400) from None


def local_range(d_from: date | None, d_to: date | None, tz) -> tuple[datetime | None, datetime | None]:
    start = datetime.combine(d_from, time.min, tzinfo=tz) if d_from else None
    end = datetime.combine(d_to + timedelta(days=1), time.min, tzinfo=tz) if d_to else None
    return start, end
