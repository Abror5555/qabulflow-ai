# syntax=docker/dockerfile:1
# QabulFlow AI — bitta image: Django API + panel (frontend/dist), Celery worker/beat va Telegram bot.
# Build konteksti — repozitoriy ildizi:  docker compose build   (yoki: docker build -f backend/Dockerfile .)

# ---------- 1) Frontend build ----------
FROM node:22-bookworm-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------- 2) Python runtime ----------
FROM python:3.13-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ffmpeg — Telegram .ogg ovozli xabarlarini STT uchun mos formatga o'tkazish
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.lock backend/requirements.lock
RUN pip install -r backend/requirements.lock

COPY backend/ backend/
COPY --from=frontend /app/frontend/dist frontend/dist

RUN useradd --create-home --uid 10001 app \
    && mkdir -p /app/var/static /app/var/media \
    && chown -R app:app /app/var

ENV DJANGO_ENV=production \
    FRONTEND_DIST=/app/frontend/dist \
    STATIC_ROOT=/app/var/static \
    MEDIA_ROOT=/app/var/media

WORKDIR /app/backend
# collectstatic DB'ga ulanmaydi; build uchun vaqtinchalik kalit ishlatiladi (runtime'da .env dagi kalit)
RUN DJANGO_SECRET_KEY=build-only-not-used-at-runtime DJANGO_ALLOWED_HOSTS=localhost \
    python manage.py collectstatic --noinput \
    && chown -R app:app /app/var/static

USER app
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health/', timeout=4).status == 200 else 1)"
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "60", "--access-logfile", "-"]
