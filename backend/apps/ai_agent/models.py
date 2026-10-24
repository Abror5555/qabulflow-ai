from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel

DEFAULT_GREETINGS = {
    "uz": "Assalomu alaykum! Men {org} AI yordamchisiman. Kurslar, narxlar, filiallar va bepul sinov darsiga yozilish bo'yicha yordam beraman.",
    "ru": "Здравствуйте! Я AI-помощник {org}. Помогу с курсами, ценами, филиалами и записью на бесплатный пробный урок.",
    "en": "Hello! I'm the {org} AI assistant. I can help with courses, prices, branches and booking a free trial lesson.",
}


def default_greetings() -> dict:
    return dict(DEFAULT_GREETINGS)


def default_languages() -> list:
    return ["uz", "ru", "en"]


def default_working_hours() -> dict:
    return {"start": "09:00", "end": "20:00", "days": [0, 1, 2, 3, 4, 5]}


def default_handoff_keywords() -> list:
    return ["operator", "administrator", "admin", "odam bilan", "оператор", "администратор", "human", "manager"]


class AISettings(TimeStampedModel):
    """Tashkilot tomonidan boshqariladigan, xavfsiz doiradagi suhbat sozlamalari.

    Narx/jadvalni uydirish, tasdiqsiz bron qilish yoki ichki hujjatlarni ochish kabi
    xavfsizlik qoidalarini o'chiradigan sozlama ataylab mavjud emas.
    """

    class Tone(models.TextChoices):
        FRIENDLY = "friendly", "Samimiy"
        FORMAL = "formal", "Rasmiy"

    organization = models.OneToOneField("organizations.Organization", on_delete=models.CASCADE, related_name="ai_settings")
    is_enabled = models.BooleanField(default=True, help_text="O'chirilsa, barcha yangi suhbatlar operatorga tushadi")
    greetings = models.JSONField(default=default_greetings)
    enabled_languages = models.JSONField(default=default_languages)
    tone = models.CharField(max_length=16, choices=Tone.choices, default=Tone.FRIENDLY)
    working_hours = models.JSONField(default=default_working_hours)
    handoff_keywords = models.JSONField(default=default_handoff_keywords)
    handoff_after_failed_attempts = models.PositiveSmallIntegerField(default=2, validators=[MinValueValidator(1), MaxValueValidator(5)])
    handoff_outside_hours_notice = models.BooleanField(default=True)
    ask_phone_before_booking = models.BooleanField(default=True)
    max_slots_to_offer = models.PositiveSmallIntegerField(default=3, validators=[MinValueValidator(1), MaxValueValidator(5)])
    reminder_hours_before = models.PositiveSmallIntegerField(default=3, validators=[MinValueValidator(1), MaxValueValidator(48)])

    def greeting_for(self, lang: str, org_name: str) -> str:
        text = (self.greetings or {}).get(lang) or DEFAULT_GREETINGS.get(lang) or DEFAULT_GREETINGS["uz"]
        return text.replace("{org}", org_name)


class AICallLog(models.Model):
    class Status(models.TextChoices):
        OK = "ok", "OK"
        ERROR = "error", "Xato"
        TIMEOUT = "timeout", "Timeout"
        BUDGET = "budget_exceeded", "Limit tugadi"

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="+")
    conversation = models.ForeignKey("conversations.Conversation", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    provider = models.CharField(max_length=32)
    model = models.CharField(max_length=128, blank=True)
    kind = models.CharField(max_length=16, default="chat")  # chat | stt
    status = models.CharField(max_length=20, choices=Status.choices)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    latency_ms = models.PositiveIntegerField(default=0)
    error_code = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at"]
