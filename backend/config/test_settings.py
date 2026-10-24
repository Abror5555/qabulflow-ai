"""Test sozlamalari: environment o'zgaruvchilari asosiy sozlamalar import qilinishidan OLDIN o'rnatiladi."""

import os
import tempfile

os.environ["DJANGO_ENV"] = "test"
os.environ["DEMO_MODE"] = "true"
os.environ["AI_PROVIDER"] = "demo"
os.environ["STT_PROVIDER"] = "demo"
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"
os.environ["TELEGRAM_BOT_TOKEN"] = ""
os.environ["TELEGRAM_MODE"] = "polling"
os.environ["AI_MODEL"] = ""
os.environ["STT_MODEL"] = ""
os.environ["ANTHROPIC_API_KEY"] = ""  # testlar hech qachon real API chaqirmaydi
os.environ["OPENAI_API_KEY"] = ""
os.environ.setdefault("MEDIA_ROOT", os.path.join(tempfile.gettempdir(), "qabulflow-test-media"))

from config.settings import *  # noqa: E402,F401,F403
