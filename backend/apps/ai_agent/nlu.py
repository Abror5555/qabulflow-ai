"""Yengil, deterministik matn tahlili: til aniqlash, tasdiq/rad, raqam va vaqt bo'lagi.

Bu yerda hech qanday LLM yo'q — server tomonidagi xavfsizlik tekshiruvlari (masalan,
bron tasdig'i) shu deterministik qoidalarga tayanadi.
"""

from __future__ import annotations

import re

APOSTROPHES = str.maketrans({"ʻ": "'", "’": "'", "`": "'", "ʼ": "'", "‘": "'"})
UZ_CYRILLIC = set("ўқғҳЎҚҒҲ")


def normalize(text: str) -> str:
    text = (text or "").translate(APOSTROPHES).lower().strip()
    return re.sub(r"\s+", " ", text)


def words(text: str) -> list[str]:
    return re.findall(r"[\w']+", normalize(text))


UZ_MARKERS = [
    "o'",
    "g'",
    "salom",
    "assalom",
    "qancha",
    "narx",
    "yozil",
    "qayer",
    "rahmat",
    "kerak",
    "bormi",
    "qanday",
    "sizlar",
    "dars",
    "bo'ladi",
    "mayli",
    "yo'q",
    "ertalab",
    "kechqurun",
    "ismim",
    "kursi",
    "kursga",
    "haqida",
    "qachon",
    "bilan",
    "uchun",
    "manzil",
    "sinov",
    "tushdan",
    "menga",
    "nechpul",
    "necha",
    "qilmoq",
    "xohlayman",
    "istayman",
    "bering",
]
EN_MARKERS = [
    "hello",
    "hi",
    "price",
    "how",
    "much",
    "course",
    "please",
    "book",
    "trial",
    "lesson",
    "thanks",
    "thank",
    "what",
    "where",
    "when",
    "want",
    "english",
    "my",
    "name",
    "is",
    "the",
    "would",
    "like",
    "can",
    "schedule",
    "cost",
    "yes",
]


def detect_language(text: str) -> str | None:
    raw = text or ""
    letters = [ch for ch in raw if ch.isalpha()]
    if len(letters) < 2:
        return None
    cyr = sum(1 for ch in letters if "Ѐ" <= ch <= "ӿ")
    if cyr / len(letters) > 0.5:
        return "uz" if any(ch in UZ_CYRILLIC for ch in raw) else "ru"
    norm = normalize(raw)
    tokens = set(words(raw))
    uz = sum(1 for m in UZ_MARKERS if (m in norm if "'" in m else m in tokens or any(t.startswith(m) for t in tokens)))
    en = sum(1 for m in EN_MARKERS if m in tokens)
    if uz == 0 and en == 0:
        return None
    return "uz" if uz >= en else "en"


YES_WORDS = {
    "ha",
    "xa",
    "haa",
    "hа",
    "albatta",
    "mayli",
    "bo'ladi",
    "boladi",
    "tasdiqlayman",
    "tasdiqlang",
    "tasdiq",
    "roziman",
    "ok",
    "okay",
    "okey",
    "yes",
    "yep",
    "yeah",
    "sure",
    "confirm",
    "confirmed",
    "да",
    "конечно",
    "хорошо",
    "ок",
    "подтверждаю",
    "давайте",
    "ага",
    "угу",
    "go",
    "yozing",
    "xop",
    "xo'p",
    "ho'p",
}
NO_WORDS = {"yo'q", "yoq", "нет", "no", "nope", "kerakmas", "emas", "не", "отмена", "bekor", "cancel", "otmena"}


def is_negative(text: str) -> bool:
    w = words(text)
    norm = normalize(text)
    return bool(w) and (w[0] in NO_WORDS or "kerak emas" in norm or "не надо" in norm or "don't" in norm)


def is_affirmative(text: str) -> bool:
    """Qisqa va aniq tasdiq ("Ha", "Да", "Yes, book it"). Inkor bo'lsa — False."""

    w = words(text)
    if not w or len(w) > 8 or is_negative(text):
        return False
    if any(x in NO_WORDS for x in w):
        return False
    return w[0] in YES_WORDS or (len(w) <= 3 and any(x in YES_WORDS for x in w))


NUMBER_WORDS = {
    "birinchi": 1,
    "ikkinchi": 2,
    "uchinchi": 3,
    "to'rtinchi": 4,
    "beshinchi": 5,
    "первый": 1,
    "первая": 1,
    "второй": 2,
    "вторая": 2,
    "третий": 3,
    "третья": 3,
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
}


def pick_number(text: str, maximum: int) -> int | None:
    norm = normalize(text)
    match = re.fullmatch(r"\D{0,12}?(\d{1,2})\s*[).]?\s*\D{0,20}", norm)
    if match:
        value = int(match.group(1))
        return value if 1 <= value <= maximum else None
    for word, value in NUMBER_WORDS.items():
        if word in norm and value <= maximum:
            return value
    return None


PART_OF_DAY = {
    "morning": ["ertalab", "tong", "ertal", "утр", "morning", "am"],
    "afternoon": ["tushdan", "kunduz", "obed", "днём", "днем", "после обеда", "afternoon", "day"],
    "evening": ["kechqurun", "kechki", "вечер", "evening", "night"],
    "any": ["farqi yo'q", "farqi yoq", "istalgan", "har qanday", "любое", "без разницы", "any", "whatever", "doesn't matter"],
}


def detect_part_of_day(text: str) -> str | None:
    norm = normalize(text)
    tokens = words(text)
    for part, markers in PART_OF_DAY.items():
        if any(_marker_hit(m, norm, tokens) for m in markers):
            return part
    return None


def _marker_hit(m: str, norm: str, tokens: list[str]) -> bool:
    if " " in m or "'" in m:
        return m in norm
    if len(m) <= 3:
        return m in tokens
    return any(t.startswith(m) for t in tokens)


def has_any(text: str, markers: list[str]) -> bool:
    norm = normalize(text)
    tokens = words(text)
    return any(_marker_hit(m, norm, tokens) for m in markers)


INTENTS = {
    "greeting": ["salom", "assalom", "привет", "здравств", "hello", "hi", "hey", "добрый"],
    "price": ["narx", "qancha", "nechpul", "necha pul", "to'lov", "цен", "стоим", "сколько", "price", "cost", "how much", "fee"],
    "courses": ["kurs", "курс", "course", "yo'nalish", "fan"],
    "branches": ["filial", "manzil", "qayer", "адрес", "филиал", "где", "branch", "address", "where", "location"],
    "schedule": ["jadval", "vaqt", "soat", "qachon", "расписан", "время", "когда", "schedule", "timetable", "when"],
    "booking": ["yozil", "yozib", "sinov", "bron", "запис", "пробн", "trial", "book", "sign up", "register"],
    "my_bookings": ["bronim", "bronlarim", "mening bron", "мои запис", "моя запис", "my booking", "my bookings"],
    "cancel": ["bekor", "отмен", "cancel"],
    "thanks": ["rahmat", "спасибо", "thank"],
}


def detect_intents(text: str) -> set[str]:
    return {name for name, markers in INTENTS.items() if has_any(text, markers)}
