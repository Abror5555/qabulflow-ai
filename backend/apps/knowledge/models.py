import uuid

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models

from apps.core.models import TimeStampedModel


def knowledge_upload_to(instance, filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"org_{instance.organization_id}/knowledge/{uuid.uuid4().hex}.{ext}"


class KnowledgeDocument(TimeStampedModel):
    class Visibility(models.TextChoices):
        CUSTOMER = "customer", "Mijozlar uchun"
        INTERNAL = "internal", "Faqat xodimlar"

    class Status(models.TextChoices):
        PENDING = "pending", "Navbatda"
        PROCESSING = "processing", "Qayta ishlanmoqda"
        INDEXED = "indexed", "Indekslandi"
        NO_TEXT = "no_text", "Matn topilmadi"
        FAILED = "failed", "Xato"

    class FileType(models.TextChoices):
        PDF = "pdf", "PDF"
        TXT = "txt", "TXT"
        MD = "md", "Markdown"

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="knowledge_documents")
    title = models.CharField(max_length=200)
    file = models.FileField(upload_to=knowledge_upload_to)
    file_type = models.CharField(max_length=8, choices=FileType.choices)
    original_filename = models.CharField(max_length=255)
    size_bytes = models.PositiveIntegerField(default=0)
    visibility = models.CharField(max_length=16, choices=Visibility.choices, default=Visibility.CUSTOMER)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    status_message = models.CharField(max_length=255, blank=True)
    page_count = models.PositiveIntegerField(default=0)
    chunk_count = models.PositiveIntegerField(default=0)
    char_count = models.PositiveIntegerField(default=0)
    flagged_lines = models.PositiveIntegerField(default=0, help_text="Ko'rsatmaga o'xshash, mijozga chiqarilmaydigan qatorlar")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    indexed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title


class KnowledgeChunk(models.Model):
    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="+")
    document = models.ForeignKey(KnowledgeDocument, on_delete=models.CASCADE, related_name="chunks")
    position = models.PositiveIntegerField()
    page_number = models.PositiveIntegerField(null=True, blank=True)
    text = models.TextField()
    visibility = models.CharField(max_length=16, choices=KnowledgeDocument.Visibility.choices)
    search_vector = SearchVectorField(null=True)

    class Meta:
        ordering = ["document", "position"]
        indexes = [
            GinIndex(fields=["search_vector"], name="kchunk_search_gin"),
            GinIndex(fields=["text"], name="kchunk_text_trgm", opclasses=["gin_trgm_ops"]),
            models.Index(fields=["organization", "visibility"]),
        ]
