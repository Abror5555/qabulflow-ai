"""QabulFlow AI — Django sozlamalari.

Barcha maxfiy va muhitga bog'liq qiymatlar environment variables orqali beriladi.
DJANGO_ENV: development | test | production
"""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent

try:  # .env faylini ixtiyoriy yuklash (lokal ishga tushirish uchun)
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:  # pragma: no cover
    pass


def env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return default if value is None or value == "" else value


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    return int(value) if value not in (None, "") else default


def env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    return float(value) if value not in (None, "") else default


def env_list(name: str, default: str = "") -> list[str]:
    raw = env(name, default) or ""
    return [item.strip() for item in raw.split(",") if item.strip()]


DJANGO_ENV = env("DJANGO_ENV", "development")
IS_PRODUCTION = DJANGO_ENV == "production"
IS_TEST = DJANGO_ENV == "test"

SECRET_KEY = env("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if IS_PRODUCTION:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY production muhitida majburiy.")
    SECRET_KEY = "dev-only-insecure-key-change-me"  # noqa: S105 - faqat development

DEBUG = False if IS_PRODUCTION else env_bool("DJANGO_DEBUG", True)

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "" if IS_PRODUCTION else "localhost,127.0.0.1,0.0.0.0,testserver")
if IS_PRODUCTION and not ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS production muhitida majburiy.")

CSRF_TRUSTED_ORIGINS = env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS", "" if IS_PRODUCTION else "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000"
)

# Demo rejimi: kalitsiz ishga tushirish, demo hisoblar, demo outbox.
DEMO_MODE = env_bool("DEMO_MODE", not IS_PRODUCTION)
DEMO_ACCOUNT_DOMAIN = "demo.qabulflow.local"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "corsheaders",
    "apps.core",
    "apps.accounts",
    "apps.organizations",
    "apps.courses",
    "apps.leads",
    "apps.conversations",
    "apps.bookings",
    "apps.knowledge",
    "apps.ai_agent",
    "apps.analytics",
    "apps.notifications",
    "apps.integrations",
]

MIDDLEWARE = [
    "apps.core.middleware.RequestIdMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.core.middleware.TenantMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

FRONTEND_DIST = Path(env("FRONTEND_DIST", str(PROJECT_ROOT / "frontend" / "dist")))

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", "qabulflow"),
        "USER": env("POSTGRES_USER", "qabulflow"),
        "PASSWORD": env("POSTGRES_PASSWORD", "qabulflow"),
        "HOST": env("POSTGRES_HOST", "127.0.0.1"),
        "PORT": env("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": env_int("POSTGRES_CONN_MAX_AGE", 60),
        "CONN_HEALTH_CHECKS": True,
        "TEST": {"NAME": env("POSTGRES_TEST_DB", "test_qabulflow")},
    }
}

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ["apps.accounts.backends.EmailBackend"]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
if IS_TEST:
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

LANGUAGE_CODE = "uz"
LANGUAGES = [("uz", "O'zbekcha"), ("ru", "Русский"), ("en", "English")]
TIME_ZONE = "UTC"  # DB va ichki hisob UTC; ko'rsatish tashkilot zonasi bo'yicha
DEFAULT_ORG_TIMEZONE = "Asia/Tashkent"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = Path(env("STATIC_ROOT", str(PROJECT_ROOT / "var" / "static")))
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage" if IS_PRODUCTION else "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
WHITENOISE_ROOT = FRONTEND_DIST if FRONTEND_DIST.exists() else None

# Maxfiy fayllar (bilim bazasi, ovozli xabarlar) public URL orqali berilmaydi.
MEDIA_ROOT = Path(env("MEDIA_ROOT", str(PROJECT_ROOT / "var" / "media")))
MEDIA_URL = "/media-private/"  # route qilinmaydi; yuklab olish faqat ruxsatli endpoint orqali

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REDIS_URL = env("REDIS_URL", "redis://127.0.0.1:6379/0")

if IS_TEST or env_bool("USE_LOCMEM_CACHE", False):
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
else:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": env("CACHE_REDIS_URL", "redis://127.0.0.1:6379/1"),
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
            "TIMEOUT": 300,
        }
    }

# --- Sessiya, cookie, xavfsizlik ---
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 12
CSRF_COOKIE_HTTPONLY = False  # SPA X-CSRFToken header uchun o'qiydi
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
DATA_UPLOAD_MAX_MEMORY_SIZE = 12 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

if IS_PRODUCTION:
    # HTTPS ortida true (standart). Faqat lokal http docker sinovi uchun DJANGO_SECURE_COOKIES=false.
    SESSION_COOKIE_SECURE = env_bool("DJANGO_SECURE_COOKIES", True)
    CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_HSTS_SECONDS = env_int("DJANGO_HSTS_SECONDS", 31536000)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = False
    SILENCED_SYSTEM_CHECKS: list[str] = []

CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "")
CORS_ALLOW_CREDENTIALS = True
CORS_URLS_REGEX = r"^/api/.*$"

# --- DRF ---
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["apps.core.permissions.IsOrganizationMember"],
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.core.exceptions.api_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.UserRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {
        "user": env("THROTTLE_USER", "1200/min"),
        "login": env("THROTTLE_LOGIN", "10/min"),
        "webchat": env("THROTTLE_WEBCHAT", "40/min"),
        "webchat_session": env("THROTTLE_WEBCHAT_SESSION", "20/min"),
        "telegram_webhook": env("THROTTLE_TELEGRAM_WEBHOOK", "600/min"),
    },
    "DATETIME_FORMAT": "iso-8601",
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "QabulFlow AI API",
    "DESCRIPTION": "O'quv markazlari uchun AI qabul, sotuv va sinov darsiga yozilish tizimi API.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": r"/api/",
    # Bir xil nomli (status, channel, language) turli choice to'plamlari uchun aniq enum nomlari
    "ENUM_NAME_OVERRIDES": {
        "LanguageEnum": LANGUAGES,
        "LanguageCodeEnum": ["uz", "ru", "en"],
        "ConversationChannelEnum": "apps.conversations.models.Conversation.Channel",
        "BookingChannelEnum": "apps.bookings.models.TrialBooking.Channel",
        "ConversationStatusEnum": "apps.conversations.models.Conversation.Status",
        "MessageSenderEnum": "apps.conversations.models.Message.Sender",
        "HandoffStatusEnum": "apps.conversations.models.HumanHandoff.Status",
        "LeadStatusEnum": "apps.leads.models.Lead.Status",
        "BookingStatusEnum": "apps.bookings.models.TrialBooking.Status",
        "EnrollmentStatusEnum": "apps.bookings.models.Enrollment.Status",
        "SlotStatusEnum": "apps.courses.models.TrialSlot.Status",
        "KnowledgeStatusEnum": "apps.knowledge.models.KnowledgeDocument.Status",
        "OutboxStatusEnum": "apps.notifications.models.OutboxMessage.Status",
        "ReminderStatusEnum": "apps.notifications.models.Reminder.Status",
        "AICallStatusEnum": "apps.ai_agent.models.AICallLog.Status",
    },
}

# --- Celery ---
CELERY_BROKER_URL = env("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", REDIS_URL)
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", IS_TEST)
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_TIME_LIMIT = 300
CELERY_TASK_SOFT_TIME_LIMIT = 240
CELERY_TIMEZONE = "UTC"
CELERY_BEAT_SCHEDULE = {
    "dispatch-due-reminders": {
        "task": "apps.notifications.tasks.dispatch_due_reminders",
        "schedule": timedelta(seconds=env_int("REMINDER_DISPATCH_INTERVAL", 60)),
    },
    "retry-failed-outbox": {
        "task": "apps.notifications.tasks.retry_pending_outbox",
        "schedule": timedelta(minutes=2),
    },
}

# --- AI provider ---
AI_PROVIDER = (env("AI_PROVIDER", "demo") or "demo").lower()  # demo | anthropic | openai
AI_MODEL = env("AI_MODEL", "")
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = env("OPENAI_API_KEY", "")
AI_TIMEOUT_SECONDS = env_float("AI_TIMEOUT_SECONDS", 30.0)
AI_MAX_RETRIES = env_int("AI_MAX_RETRIES", 2)
AI_MAX_OUTPUT_TOKENS = env_int("AI_MAX_OUTPUT_TOKENS", 700)
AI_MAX_TOOL_ITERATIONS = env_int("AI_MAX_TOOL_ITERATIONS", 6)
AI_DAILY_TOKEN_BUDGET_PER_CONVERSATION = env_int("AI_DAILY_TOKEN_BUDGET_PER_CONVERSATION", 60000)
AI_HISTORY_MESSAGES = env_int("AI_HISTORY_MESSAGES", 16)

# --- Speech-to-text ---
STT_PROVIDER = (env("STT_PROVIDER", "demo") or "demo").lower()  # demo | openai
STT_MODEL = env("STT_MODEL", "")
STT_MIN_CONFIDENCE = env_float("STT_MIN_CONFIDENCE", 0.6)
AUDIO_MAX_BYTES = env_int("AUDIO_MAX_BYTES", 10 * 1024 * 1024)
AUDIO_MAX_SECONDS = env_int("AUDIO_MAX_SECONDS", 120)

# --- Telegram ---
TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_MODE = (env("TELEGRAM_MODE", "polling") or "polling").lower()  # polling | webhook
TELEGRAM_ORGANIZATION_SLUG = env("TELEGRAM_ORGANIZATION_SLUG", "demo-academy")
TELEGRAM_WEBHOOK_SECRET = env("TELEGRAM_WEBHOOK_SECRET", "")
TELEGRAM_WEBHOOK_PATH_TOKEN = env("TELEGRAM_WEBHOOK_PATH_TOKEN", "")
TELEGRAM_WEBHOOK_BASE_URL = env("TELEGRAM_WEBHOOK_BASE_URL", "")
if TELEGRAM_MODE not in {"polling", "webhook"}:
    raise ImproperlyConfigured("TELEGRAM_MODE faqat 'polling' yoki 'webhook' bo'lishi mumkin.")

# --- Bilim bazasi ---
KNOWLEDGE_MAX_BYTES = env_int("KNOWLEDGE_MAX_BYTES", 10 * 1024 * 1024)
KNOWLEDGE_CHUNK_SIZE = env_int("KNOWLEDGE_CHUNK_SIZE", 900)
KNOWLEDGE_CHUNK_OVERLAP = env_int("KNOWLEDGE_CHUNK_OVERLAP", 120)

PUBLIC_BASE_URL = env("PUBLIC_BASE_URL", "http://localhost:8000")

# --- Logging (maxfiy qiymatlar redaksiya qilinadi) ---
LOG_LEVEL = env("LOG_LEVEL", "INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "redact": {"()": "apps.core.logging.RedactingFilter"},
        "request_id": {"()": "apps.core.logging.RequestIdFilter"},
    },
    "formatters": {
        "standard": {"format": "%(asctime)s %(levelname)s [%(name)s] [rid=%(request_id)s] %(message)s"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "filters": ["redact", "request_id"],
        }
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django.db.backends": {"level": "WARNING"},
        "httpx": {"level": "WARNING"},
        "aiogram": {"level": "INFO"},
    },
}
