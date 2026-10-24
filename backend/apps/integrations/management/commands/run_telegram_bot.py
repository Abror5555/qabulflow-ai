"""Development uchun Telegram long polling.

    python manage.py run_telegram_bot

Webhook rejimida (TELEGRAM_MODE=webhook) ishga tushmaydi — ikkalasi bir vaqtda ishlatilmaydi.
"""

import asyncio

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Telegram botni long polling rejimida ishga tushiradi (faqat TELEGRAM_MODE=polling)."

    def handle(self, *args, **options):
        if not settings.TELEGRAM_BOT_TOKEN:
            raise CommandError("TELEGRAM_BOT_TOKEN kiritilmagan. .env faylida tokenni ko'rsating.")
        if settings.DEMO_MODE:
            raise CommandError("DEMO_MODE=true: demo rejimida real Telegram foydalanuvchilariga xabar yuborilmaydi. DEMO_MODE=false qiling.")
        if settings.TELEGRAM_MODE != "polling":
            raise CommandError("TELEGRAM_MODE=webhook: polling va webhook bir vaqtda ishlatilmaydi.")
        from apps.integrations.telegram.bot import run_polling
        from apps.integrations.telegram.processor import get_bot_organization

        org = get_bot_organization()
        self.stdout.write(self.style.SUCCESS(f"Bot tashkiloti: {org.name} ({org.slug}). Long polling boshlanmoqda..."))
        asyncio.run(run_polling())
