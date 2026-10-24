"""Speech-to-text adapterlari va audio tekshiruvi.

* DemoSTT — haqiqiy transkripsiya EMAS: belgilangan demo matn qaytaradi (is_demo=True).
* OpenAISTT — rasmiy `openai` SDK orqali /v1/audio/transcriptions endpointi.
"""

from __future__ import annotations

import io
import logging
import math
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass

from django.conf import settings

from apps.ai_agent.providers.base import AIProviderError

logger = logging.getLogger(__name__)

ALLOWED_AUDIO_TYPES = {
    "audio/ogg": "ogg",
    "audio/opus": "ogg",
    "audio/oga": "ogg",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/mp4": "m4a",
    "audio/x-m4a": "m4a",
    "audio/m4a": "m4a",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/wave": "wav",
    "audio/webm": "webm",
    "video/webm": "webm",
}
OPENAI_NATIVE_FORMATS = {"mp3", "m4a", "wav", "webm", "mp4", "mpeg", "mpga"}


class AudioRejected(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code  # too_large | too_long | bad_format


@dataclass
class AudioInput:
    data: bytes
    content_type: str
    duration_seconds: float | None = None
    filename: str = "voice"


@dataclass
class Transcript:
    text: str
    confidence: float | None
    language: str | None
    is_demo: bool
    provider: str
    model: str = ""
    latency_ms: int = 0


def _sniff_format(data: bytes) -> str | None:
    if data[:4] == b"OggS":
        return "ogg"
    if data[:3] == b"ID3" or (len(data) > 1 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0):
        return "mp3"
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "wav"
    if data[:4] == b"\x1aE\xdf\xa3":
        return "webm"
    if data[4:8] == b"ftyp":
        return "m4a"
    return None


def probe_duration(data: bytes) -> float | None:
    try:
        import mutagen

        f = mutagen.File(io.BytesIO(data))
        if f is not None and getattr(f, "info", None) is not None and getattr(f.info, "length", None):
            return float(f.info.length)
    except Exception:  # noqa: BLE001
        pass
    if shutil.which("ffprobe"):
        try:
            with tempfile.NamedTemporaryFile(suffix=".bin") as tmp:
                tmp.write(data)
                tmp.flush()
                out = subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", tmp.name],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                value = out.stdout.strip()
                if value and value != "N/A":
                    return float(value)
        except Exception:  # noqa: BLE001
            return None
    return None


def validate_audio(audio: AudioInput) -> str:
    """Hajm, tur va davomiylikni tekshiradi. Format nomini qaytaradi."""

    if len(audio.data) > settings.AUDIO_MAX_BYTES:
        raise AudioRejected("too_large")
    if len(audio.data) < 64:
        raise AudioRejected("bad_format")
    declared = (audio.content_type or "").split(";")[0].strip().lower()
    sniffed = _sniff_format(audio.data)
    if sniffed is None or (declared and declared not in ALLOWED_AUDIO_TYPES):
        raise AudioRejected("bad_format")
    duration = audio.duration_seconds
    if duration is None:
        duration = probe_duration(audio.data)
        audio.duration_seconds = duration
    if duration is not None and duration > settings.AUDIO_MAX_SECONDS:
        raise AudioRejected("too_long")
    return sniffed


class DemoSTT:
    name = "demo"
    DEMO_TEXT = {
        "uz": "IELTS kursi narxi qancha?",
        "ru": "Сколько стоит курс IELTS?",
        "en": "How much is the IELTS course?",
    }

    def transcribe(self, audio: AudioInput, *, language_hint: str = "uz") -> Transcript:
        return Transcript(
            text=self.DEMO_TEXT.get(language_hint, self.DEMO_TEXT["uz"]),
            confidence=0.93,
            language=language_hint,
            is_demo=True,
            provider=self.name,
        )


def _convert_to_mp3(data: bytes) -> bytes:
    if not shutil.which("ffmpeg"):
        return data
    with tempfile.NamedTemporaryFile(suffix=".in") as src, tempfile.NamedTemporaryFile(suffix=".mp3") as dst:
        src.write(data)
        src.flush()
        proc = subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", src.name, "-ac", "1", "-ar", "16000", "-b:a", "48k", dst.name],
            capture_output=True,
            timeout=60,
            check=False,
        )
        if proc.returncode != 0:
            raise AIProviderError("audio_convert_failed")
        return open(dst.name, "rb").read()


class OpenAISTT:
    name = "openai"

    def __init__(self, *, api_key: str | None = None, model: str | None = None, client=None):
        self.api_key = api_key if api_key is not None else settings.OPENAI_API_KEY
        self.model = model if model is not None else settings.STT_MODEL
        if not self.api_key or not self.model:
            raise AIProviderError("not_configured", "OPENAI_API_KEY yoki STT_MODEL kiritilmagan")
        if client is None:
            import openai

            client = openai.OpenAI(api_key=self.api_key, timeout=settings.AI_TIMEOUT_SECONDS, max_retries=settings.AI_MAX_RETRIES)
        self.client = client

    def transcribe(self, audio: AudioInput, *, language_hint: str = "uz") -> Transcript:
        import openai

        fmt = _sniff_format(audio.data) or "ogg"
        data, ext = audio.data, fmt
        if fmt not in OPENAI_NATIVE_FORMATS:
            data, ext = _convert_to_mp3(audio.data), "mp3"
        started = time.monotonic()
        kwargs = {"model": self.model, "file": (f"voice.{ext}", data)}
        verbose = self.model == "whisper-1"
        if verbose:
            kwargs["response_format"] = "verbose_json"
        if language_hint in {"uz", "ru", "en"}:
            kwargs["language"] = language_hint
        try:
            response = self.client.audio.transcriptions.create(**kwargs)
        except openai.APITimeoutError as exc:
            raise AIProviderError("timeout") from exc
        except openai.APIStatusError as exc:
            raise AIProviderError(f"http_{getattr(exc, 'status_code', 'error')}") from exc
        except openai.APIConnectionError as exc:
            raise AIProviderError("connection_error") from exc
        latency = int((time.monotonic() - started) * 1000)
        text = (getattr(response, "text", "") or "").strip()
        confidence = None
        segments = getattr(response, "segments", None) or []
        if segments:
            logprobs = [getattr(s, "avg_logprob", None) for s in segments]
            no_speech = [getattr(s, "no_speech_prob", 0) or 0 for s in segments]
            logprobs = [lp for lp in logprobs if lp is not None]
            if logprobs:
                confidence = math.exp(sum(logprobs) / len(logprobs)) * (1 - max(no_speech))
        if confidence is None:
            confidence = 0.8 if len(text.split()) >= 2 else 0.4
        return Transcript(
            text=text,
            confidence=round(confidence, 3),
            language=getattr(response, "language", None) or language_hint,
            is_demo=False,
            provider=self.name,
            model=self.model,
            latency_ms=latency,
        )


def get_stt_provider():
    provider = settings.STT_PROVIDER
    if provider == "demo":
        return DemoSTT()
    if provider == "openai":
        return OpenAISTT()
    raise AIProviderError("not_configured", f"Noma'lum STT_PROVIDER: {provider}")
