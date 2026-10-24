"""LLM javobi uchun server tomonidagi chiqish tekshiruvlari.

1. Bron/bekor qilish haqidagi da'vo tegishli tool muvaffaqiyatli bo'lmasa — almashtiriladi.
2. Pulga o'xshash raqamlar (narx, chegirma) shu navbatdagi tool natijalarida bo'lmasa — almashtiriladi.
"""

from __future__ import annotations

import re

from apps.ai_agent.texts import t

BOOKED_CLAIMS = [
    r"yozildingiz",
    r"yozib qo'ydim",
    r"yozib qoydim",
    r"bron qilindi",
    r"bron qildim",
    r"bron tasdiqlandi",
    r"ro'yxatga oldim",
    r"вы записаны",
    r"записал[аи]? вас",
    r"запись (создана|подтверждена|оформлена)",
    r"забронировал",
    r"you(?:'re| are) booked",
    r"booking (?:is )?confirmed",
    r"i(?:'ve| have) booked",
    r"booked you",
]
CANCEL_CLAIMS = [r"bekor qilindi", r"bekor qildim", r"отменен[аo]?", r"отменил", r"(?:is|was|has been) cancell?ed", r"i(?:'ve| have) cancell?ed"]
_BOOKED_RE = re.compile("|".join(BOOKED_CLAIMS), re.IGNORECASE)
_CANCEL_RE = re.compile("|".join(CANCEL_CLAIMS), re.IGNORECASE)
_MONEY_RE = re.compile(
    r"(\d[\d\s.,]*\d|\d)\s*(?:so['ʻ’]?m|sum|сум|uzs|\$|usd|долл|dollar|%|foiz|процент|percent)"
    r"|(?:\$|uzs)\s*(\d[\d\s.,]*\d|\d)",
    re.IGNORECASE,
)
_BIG_NUMBER_RE = re.compile(r"\b\d{1,3}(?:[ ,.]\d{3})+\b|\b\d{5,}\b")


def _digits(value: str) -> str:
    d = re.sub(r"\D", "", value or "")
    return d.lstrip("0") or "0"


_PHONE_RE = re.compile(r"\+?998[\s-]?\(?\d{2}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}")


def find_unbacked_numbers(text: str, allowed: set[str]) -> list[str]:
    text = _PHONE_RE.sub(" ", text)
    found = []
    for m in _MONEY_RE.finditer(text):
        raw = m.group(1) or m.group(2) or ""
        if raw and _digits(raw) not in allowed:
            found.append(raw.strip())
    for m in _BIG_NUMBER_RE.finditer(text):
        if _digits(m.group(0)) not in allowed:
            found.append(m.group(0))
    return found


def apply_output_guards(text: str, executor, lang: str) -> tuple[str, list[str]]:
    flags: list[str] = []
    booked_ok = "create_trial_booking" in executor.successful
    cancel_ok = "cancel_trial_booking" in executor.successful
    if _BOOKED_RE.search(text) and not booked_ok:
        flags.append("unbacked_booking_claim")
        return t("booking_not_done", lang), flags
    if _CANCEL_RE.search(text) and not cancel_ok and not booked_ok:
        flags.append("unbacked_cancel_claim")
        return t("clarify", lang), flags
    unbacked = find_unbacked_numbers(text, executor.allowed_numbers)
    if unbacked:
        flags.append("unbacked_numbers")
        return t("price_unavailable", lang), flags
    return text, flags
