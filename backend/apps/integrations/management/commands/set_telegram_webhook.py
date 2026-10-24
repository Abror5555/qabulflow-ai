"""Production uchun himoyalangan webhook'ni o'rnatadi yoki o'chiradi.

python manage.py set_telegram_webhook          # o'rnatish
python manage.py set_telegram_webhook --delete # o'chirish (polling'ga qaytish uchun)
"""

import asyncio

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Telegram webhook URL va secret_token'ni o'rnatadi (TELEGRAM_MODE=webhook)."

    def add_arguments(self, parser):
        parser.add_argument("--delete", action="store_true")

    def handle(self, *args, **options):
        from aiogram import Bot

        if not settings.TELEGRAM_BOT_TOKEN:
            raise CommandError("TELEGRAM_BOT_TOKEN kiritilmagan.")

        async def run():
            bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
            try:
                if options["delete"]:
                    await bot.delete_webhook(drop_pending_updates=False)
                    return "Webhook o'chirildi."
                if settings.TELEGRAM_MODE != "webhook":
                    raise CommandError("TELEGRAM_MODE=webhook bo'lishi kerak.")
                if not (
                    settings.TELEGRAM_WEBHOOK_BASE_URL.startswith("https://") and settings.TELEGRAM_WEBHOOK_SECRET and settings.TELEGRAM_WEBHOOK_PATH_TOKEN
                ):
                    raise CommandError("TELEGRAM_WEBHOOK_BASE_URL (https), TELEGRAM_WEBHOOK_SECRET va TELEGRAM_WEBHOOK_PATH_TOKEN majburiy.")
                url = settings.TELEGRAM_WEBHOOK_BASE_URL.rstrip("/") + f"/api/integrations/telegram/webhook/{settings.TELEGRAM_WEBHOOK_PATH_TOKEN}/"
                await bot.set_webhook(
                    url, secret_token=settings.TELEGRAM_WEBHOOK_SECRET, allowed_updates=["message", "callback_query"], drop_pending_updates=False
                )
                return "Webhook o'rnatildi (URL maxfiy yo'l bilan)."
            finally:
                await bot.session.close()

        self.stdout.write(self.style.SUCCESS(asyncio.run(run())))
