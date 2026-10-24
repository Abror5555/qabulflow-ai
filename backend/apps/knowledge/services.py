"""Bilim bazasi: fayl tekshiruvi, matn ajratish, chunklash, indekslash va qidiruv.

Qidiruv PostgreSQL full-text (config='simple', prefix so'rovlar) + pg_trgm
o'xshashlik orqali amalga oshiriladi. Vektor baza talab qilinmaydi.
"""

from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass

from django.conf import settings
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector, TrigramWordSimilarity
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from apps.core.exceptions import BusinessError
from apps.knowledge.models import KnowledgeChunk, KnowledgeDocument

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {"pdf": "pdf", "txt": "txt", "md": "md", "markdown": "md"}

# Hujjat ichidagi AI'ga qaratilgan ko'rsatmalarga o'xshash qatorlar mijozga chiqarilmaydi
# va tizim ko'rsatmasi sifatida hech qachon bajarilmaydi.
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+|any\s+)?(previous|prior|above|the)\b",
    r"disregard\s+(all\s+|the\s+)?(previous|prior|above|instructions)",
    r"system\s*prompt",
    r"you\s+are\s+now\b",
    r"\bact\s+as\b",
    r"developer\s+mode",
    r"^\s*(system|assistant|user)\s*:",
    r"new\s+instructions?",
    r"игнорир\w*\s+(все\s+)?(предыдущ|инструкц)",
    r"забудь\w*\s+(все\s+)?(предыдущ|инструкц)",
    r"системн\w+\s+промпт",
    r"oldingi\s+ko['ʻ’`]?rsatma",
    r"ko['ʻ’`]?rsatmalarni\s+(e['ʻ’`]?tiborsiz|unut)",
    r"barcha\s+ko['ʻ’`]?rsatmalarni",
]
_INJECTION_RE = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE | re.MULTILINE)
_TERM_RE = re.compile(r"[\w']+", re.UNICODE)
STOPWORDS = {
    "va",
    "bu",
    "u",
    "men",
    "siz",
    "qanday",
    "nima",
    "uchun",
    "bilan",
    "ham",
    "bormi",
    "qancha",
    "haqida",
    "kerak",
    "и",
    "в",
    "на",
    "с",
    "по",
    "как",
    "что",
    "это",
    "у",
    "вас",
    "есть",
    "ли",
    "для",
    "the",
    "a",
    "an",
    "is",
    "are",
    "of",
    "to",
    "in",
    "for",
    "and",
    "do",
    "you",
    "what",
    "how",
    "can",
    "i",
    "your",
}


@dataclass
class ExtractedPage:
    page: int | None
    text: str


def detect_file_type(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise BusinessError("unsupported_file", "Faqat PDF, TXT yoki Markdown (.md) fayl yuklash mumkin.", status_code=400)
    return ALLOWED_EXTENSIONS[ext]


def validate_upload(uploaded_file) -> str:
    if uploaded_file.size > settings.KNOWLEDGE_MAX_BYTES:
        mb = settings.KNOWLEDGE_MAX_BYTES // (1024 * 1024)
        raise BusinessError("file_too_large", f"Fayl hajmi {mb} MB dan oshmasligi kerak.", status_code=400)
    if uploaded_file.size == 0:
        raise BusinessError("empty_file", "Fayl bo'sh.", status_code=400)
    file_type = detect_file_type(uploaded_file.name)
    head = uploaded_file.read(2048)
    uploaded_file.seek(0)
    if file_type == "pdf":
        if not head.startswith(b"%PDF-"):
            raise BusinessError("invalid_pdf", "Fayl haqiqiy PDF emas.", status_code=400)
    else:
        if b"\x00" in head:
            raise BusinessError("invalid_text", "Matnli fayl ikkilik (binary) ma'lumotga o'xshaydi.", status_code=400)
    return file_type


def _decode_text(data: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", errors="replace")


def extract_pages(document: KnowledgeDocument) -> list[ExtractedPage]:
    document.file.open("rb")
    try:
        data = document.file.read()
    finally:
        document.file.close()
    if document.file_type == "pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception as exc:  # noqa: BLE001
                raise BusinessError("pdf_encrypted", "PDF parol bilan himoyalangan.") from exc
        pages = []
        for idx, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception:  # noqa: BLE001
                text = ""
            pages.append(ExtractedPage(idx, text))
        return pages
    text = _decode_text(data)
    if document.file_type == "md":
        text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
        text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
        text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
        text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"[*_]{1,3}([^*_]+)[*_]{1,3}", r"\1", text)
    return [ExtractedPage(None, text)]


def sanitize_for_customer(text: str) -> tuple[str, int]:
    """Ko'rsatmaga o'xshash qatorlarni olib tashlaydi. (toza_matn, olib_tashlangan_qatorlar_soni)."""

    kept, flagged = [], 0
    for line in text.splitlines():
        if _INJECTION_RE.search(line):
            flagged += 1
            continue
        kept.append(line)
    return "\n".join(kept), flagged


def _normalize(text: str) -> str:
    text = text.replace("\r", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, size: int | None = None, overlap: int | None = None) -> list[str]:
    size = size or settings.KNOWLEDGE_CHUNK_SIZE
    overlap = overlap if overlap is not None else settings.KNOWLEDGE_CHUNK_OVERLAP
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        while len(para) > size:
            cut = para.rfind(" ", 0, size)
            cut = cut if cut > size // 2 else size
            piece, para = para[:cut].strip(), para[cut:].strip()
            if current:
                chunks.append(current)
                current = ""
            chunks.append(piece)
        if len(current) + len(para) + 2 <= size:
            current = f"{current}\n\n{para}" if current else para
        else:
            if current:
                chunks.append(current)
            tail = current[-overlap:] if overlap and current else ""
            tail = tail[tail.find(" ") + 1 :] if " " in tail else tail
            current = f"{tail} {para}".strip() if tail else para
    if current:
        chunks.append(current)
    return chunks


def process_document(document_id: int) -> KnowledgeDocument:
    """Matnni ajratadi, chunklaydi va indekslaydi. Celery vazifasidan chaqiriladi."""

    document = KnowledgeDocument.objects.get(pk=document_id)
    KnowledgeDocument.objects.filter(pk=document.pk).update(status=KnowledgeDocument.Status.PROCESSING, status_message="")
    try:
        pages = extract_pages(document)
    except BusinessError as exc:
        return _finish(document, KnowledgeDocument.Status.FAILED, exc.message)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Hujjat #%s o'qilmadi: %s", document.pk, exc.__class__.__name__)
        return _finish(document, KnowledgeDocument.Status.FAILED, "Faylni o'qib bo'lmadi. Fayl buzilgan bo'lishi mumkin.")

    total_flagged = 0
    rows: list[tuple[int | None, str]] = []
    total_chars = 0
    for page in pages:
        clean, flagged = sanitize_for_customer(_normalize(page.text))
        total_flagged += flagged
        total_chars += len(clean)
        for piece in chunk_text(clean):
            if len(piece) >= 20:
                rows.append((page.page, piece))

    page_count = len(pages) if document.file_type == "pdf" else 0
    if total_chars < 40 or not rows:
        message = (
            "PDF ichidan matn topilmadi — ehtimol skaner qilingan rasm. Matnli PDF, TXT yoki Markdown yuklang."
            if document.file_type == "pdf"
            else "Faylda indekslash uchun yetarli matn yo'q."
        )
        KnowledgeChunk.objects.filter(document=document).delete()
        return _finish(document, KnowledgeDocument.Status.NO_TEXT, message, page_count=page_count, flagged=total_flagged)

    with transaction.atomic():
        KnowledgeChunk.objects.filter(document=document).delete()
        KnowledgeChunk.objects.bulk_create(
            [
                KnowledgeChunk(
                    organization_id=document.organization_id,
                    document=document,
                    position=i,
                    page_number=page_no,
                    text=text,
                    visibility=document.visibility,
                )
                for i, (page_no, text) in enumerate(rows)
            ]
        )
        KnowledgeChunk.objects.filter(document=document).update(search_vector=SearchVector("text", config="simple"))
    return _finish(document, KnowledgeDocument.Status.INDEXED, "", page_count=page_count, chunk_count=len(rows), char_count=total_chars, flagged=total_flagged)


def _finish(document, status, message, *, page_count=0, chunk_count=0, char_count=0, flagged=0):
    KnowledgeDocument.objects.filter(pk=document.pk).update(
        status=status,
        status_message=message[:255],
        page_count=page_count,
        chunk_count=chunk_count,
        char_count=char_count,
        flagged_lines=flagged,
        indexed_at=timezone.now() if status == KnowledgeDocument.Status.INDEXED else None,
    )
    document.refresh_from_db()
    return document


def set_visibility(document: KnowledgeDocument, visibility: str) -> KnowledgeDocument:
    if visibility not in KnowledgeDocument.Visibility.values:
        raise BusinessError("invalid_visibility", "Noto'g'ri ko'rinish darajasi.", status_code=400)
    document.visibility = visibility
    document.save(update_fields=["visibility", "updated_at"])
    KnowledgeChunk.objects.filter(document=document).update(visibility=visibility)
    return document


def _terms(query: str) -> list[str]:
    terms = []
    for raw in _TERM_RE.findall(query.lower()):
        term = re.sub(r"[^\w]", "", raw)
        if len(term) < 2 or term in STOPWORDS:
            continue
        terms.append(term[:30])
    return list(dict.fromkeys(terms))[:8]


@dataclass
class SearchHit:
    chunk_id: int
    document_id: int
    document_title: str
    page_number: int | None
    visibility: str
    snippet: str
    score: float


def _line_score(line: str, terms: list[str]) -> int:
    words = re.findall(r"[\w']+", line.lower())
    return sum(1 for t in terms if any(w.startswith(t) for w in words))


def _snippet(text: str, terms: list[str], width: int = 420) -> str:
    """Eng mos qator(lar)ni qaytaradi: sarlavha + mos qator + keyingi mos qatorlar."""

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return ""
    scores = [_line_score(ln, terms) for ln in lines]
    best = max(range(len(lines)), key=lambda i: (scores[i], -i))
    if scores[best] == 0:
        snippet = text[:width].strip()
        return snippet + ("…" if len(text) > width else "")
    parts = [lines[best]]
    if best > 0 and len(lines[best - 1]) < 60 and not lines[best - 1].endswith((".", "!", "?")):
        parts.insert(0, lines[best - 1])
    j = best + 1
    while j < len(lines) and scores[j] > 0 and sum(len(p) for p in parts) + len(lines[j]) < width:
        parts.append(lines[j])
        j += 1
    snippet = "\n".join(parts)
    return snippet if len(snippet) <= width else snippet[: width - 1].rstrip() + "…"


def search(organization, query: str, *, audience: str = "customer", limit: int = 5) -> list[SearchHit]:
    """audience='customer' — faqat mijozlar uchun ochiq hujjatlar; 'staff' — barchasi."""

    terms = _terms(query or "")
    if not terms:
        return []
    base = KnowledgeChunk.objects.filter(organization=organization, document__status=KnowledgeDocument.Status.INDEXED).select_related("document")
    if audience != "staff":
        base = base.filter(visibility=KnowledgeDocument.Visibility.CUSTOMER, document__visibility=KnowledgeDocument.Visibility.CUSTOMER)

    raw = " | ".join(f"{t}:*" for t in terms)
    ts_query = SearchQuery(raw, search_type="raw", config="simple")
    fts = list(base.filter(search_vector=ts_query).annotate(score=SearchRank(F("search_vector"), ts_query)).order_by("-score", "id")[: limit * 2])
    hits = {c.id: c for c in fts}
    if len(hits) < limit:
        trigram = (
            base.exclude(id__in=list(hits))
            .annotate(score=TrigramWordSimilarity(" ".join(terms), "text"))
            .filter(score__gte=0.35)
            .order_by("-score", "id")[:limit]
        )
        for c in trigram:
            hits[c.id] = c
    ranked = sorted(hits.values(), key=lambda c: (-float(c.score or 0), c.id))[:limit]
    results = []
    for c in ranked:
        snippet = _snippet(c.text, terms)
        if audience != "staff":
            snippet, _ = sanitize_for_customer(snippet)
        results.append(
            SearchHit(
                chunk_id=c.id,
                document_id=c.document_id,
                document_title=c.document.title,
                page_number=c.page_number,
                visibility=c.visibility,
                snippet=snippet,
                score=round(float(c.score or 0), 4),
            )
        )
    return results


def queue_processing(document: KnowledgeDocument) -> None:
    from apps.knowledge.tasks import process_knowledge_document

    KnowledgeDocument.objects.filter(pk=document.pk).update(status=KnowledgeDocument.Status.PENDING, status_message="")
    transaction.on_commit(lambda: process_knowledge_document.delay(document.pk))


def document_filter_q(audience: str) -> Q:
    return Q() if audience == "staff" else Q(visibility=KnowledgeDocument.Visibility.CUSTOMER)
