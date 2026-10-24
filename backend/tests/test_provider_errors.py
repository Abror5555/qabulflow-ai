"""8. AI yoki speech provider xatosida tushunarli javob va mijoz xabarining saqlanishi."""

import io
import json
import math
import struct
import wave
from types import SimpleNamespace

import pytest
from django.test import override_settings

from apps.ai_agent.models import AICallLog
from apps.ai_agent.providers.anthropic_provider import AnthropicProvider
from apps.ai_agent.providers.base import AIProviderError, ChatTurn
from apps.ai_agent.providers.openai_provider import OpenAIProvider
from apps.ai_agent.stt import Transcript
from apps.ai_agent.tools import TOOL_SPECS
from apps.bookings.models import TrialBooking
from apps.conversations import inbound
from apps.conversations.models import Message
from apps.notifications.models import Notification

pytestmark = pytest.mark.django_db


def wav_bytes(seconds=1.0, rate=8000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = b"".join(struct.pack("<h", int(3000 * math.sin(2 * math.pi * 440 * i / rate))) for i in range(int(seconds * rate)))
        w.writeframes(frames)
    return buf.getvalue()


class FailingProvider:
    name = "failing"

    def run(self, **kwargs):
        raise AIProviderError("timeout")


def test_ai_failure_keeps_message_and_replies_clearly(kit):
    conv = inbound.get_webchat_conversation(kit.org, visitor_id="web_e1")
    result = inbound.process_text(conv, "IELTS narxi qancha?", provider=FailingProvider())
    msg = Message.objects.get(pk=result.customer_message.pk)
    assert msg.text == "IELTS narxi qancha?" and msg.ai_status == "failed"
    assert len(result.replies) == 1 and "administrator xabardor" in result.replies[0].text
    assert AICallLog.objects.filter(conversation=conv, status="timeout", error_code="timeout").exists()
    assert Notification.objects.filter(organization=kit.org, kind="ai_error").exists()
    conv.refresh_from_db()
    assert conv.needs_attention


@override_settings(AI_PROVIDER="anthropic", ANTHROPIC_API_KEY="", AI_MODEL="")
def test_missing_key_is_not_silently_demo(kit):
    conv = inbound.get_webchat_conversation(kit.org, visitor_id="web_e2")
    result = inbound.process_text(conv, "Salom")
    assert result.replies[0].ai_status == "failed"
    assert result.replies[0].is_demo is False
    assert AICallLog.objects.filter(conversation=conv, error_code="not_configured").exists()


class FailingSTT:
    name = "stt-fail"

    def transcribe(self, audio, language_hint="uz"):
        raise AIProviderError("http_503")


class LowConfidenceSTT:
    name = "stt-low"

    def transcribe(self, audio, language_hint="uz"):
        return Transcript(text="ha yoziling", confidence=0.2, language="uz", is_demo=False, provider="stt-low")


def test_stt_failure_keeps_voice_message(kit):
    from apps.ai_agent.stt import AudioInput

    conv = inbound.get_webchat_conversation(kit.org, visitor_id="web_e3")
    result = inbound.process_voice(conv, AudioInput(data=wav_bytes(), content_type="audio/wav"), stt=FailingSTT())
    msg = Message.objects.get(pk=result.customer_message.pk)
    assert msg.kind == "voice" and msg.transcript_status == "failed"
    assert msg.attachments.count() == 1  # audio saqlangan
    assert "matn bilan yozing" in result.replies[0].text


def test_low_confidence_transcript_asks_clarification_no_booking(kit):
    from apps.ai_agent.stt import AudioInput

    slot = kit.slot()
    conv = inbound.get_webchat_conversation(kit.org, visitor_id="web_e4")
    conv.state = {"stage": "await_confirm", "selected_slot": slot.id, "pending_booking": {"slot_id": slot.id, "after_message_id": 0}}
    conv.save()
    result = inbound.process_voice(conv, AudioInput(data=wav_bytes(), content_type="audio/wav"), stt=LowConfidenceSTT())
    msg = Message.objects.get(pk=result.customer_message.pk)
    assert msg.transcript_status == "low_confidence"
    assert "aniq tushuna olmadim" in result.replies[0].text
    assert not TrialBooking.objects.exists()


def test_demo_transcript_is_labeled(kit):
    from apps.ai_agent.stt import AudioInput

    conv = inbound.get_webchat_conversation(kit.org, visitor_id="web_e5")
    result = inbound.process_voice(conv, AudioInput(data=wav_bytes(), content_type="audio/wav"))
    msg = Message.objects.get(pk=result.customer_message.pk)
    assert msg.is_demo is True and msg.transcript_status == "ok"
    assert "1 200 000" in result.replies[0].text


@override_settings(AUDIO_MAX_SECONDS=2)
def test_audio_limits(kit):
    from apps.ai_agent.stt import AudioInput

    conv = inbound.get_webchat_conversation(kit.org, visitor_id="web_e6")
    too_long = inbound.process_voice(conv, AudioInput(data=wav_bytes(seconds=3), content_type="audio/wav"))
    assert Message.objects.get(pk=too_long.customer_message.pk).transcript_status == "rejected"
    assert "juda uzun" in too_long.replies[0].text
    bad = inbound.process_voice(conv, AudioInput(data=b"not audio at all" * 10, content_type="audio/ogg"))
    assert Message.objects.get(pk=bad.customer_message.pk).transcript_status == "rejected"
    assert "matn bilan" in bad.replies[0].text


# ---------------------------------------------------------------- real provider adapters (mocked SDK clients)
class FakeAnthropicClient:
    def __init__(self, slot_id):
        self.calls = []
        self.slot_id = slot_id
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        usage = SimpleNamespace(input_tokens=50, output_tokens=10)
        if len(self.calls) == 1:
            block = SimpleNamespace(type="tool_use", id="tu_1", name="list_courses", input={"organization_id": 999})
            return SimpleNamespace(stop_reason="tool_use", content=[block], usage=usage)
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="IELTS Intensive — 1 200 000 so'm oyiga.")], usage=usage)


def test_anthropic_adapter_tool_loop(kit):
    client = FakeAnthropicClient(slot_id=None)
    provider = AnthropicProvider(api_key="test", model="test-model", client=client)
    executed = []

    def execute(name, args):
        executed.append((name, args))
        return {"ok": True, "courses": [{"name": "IELTS Intensive", "price": "1200000"}]}

    result = provider.run(system="sys", history=[ChatTurn("user", "narx?")], tool_specs=TOOL_SPECS, execute=execute)
    assert result.text.startswith("IELTS") and result.input_tokens == 100
    assert executed == [("list_courses", {"organization_id": 999})]
    second = client.calls[1]["messages"]
    assert second[-1]["role"] == "user" and second[-1]["content"][0]["type"] == "tool_result"
    assert json.loads(second[-1]["content"][0]["content"])["ok"] is True


class FakeOpenAIClient:
    def __init__(self):
        self.calls = []
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kwargs):
        self.calls.append(kwargs)
        usage = SimpleNamespace(prompt_tokens=40, completion_tokens=8)
        if len(self.calls) == 1:
            tc = SimpleNamespace(id="call_1", function=SimpleNamespace(name="list_branches", arguments="{}"))
            msg = SimpleNamespace(content=None, tool_calls=[tc])
        else:
            msg = SimpleNamespace(content="Filiallar: Markaz.", tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=usage)


def test_openai_adapter_tool_loop():
    client = FakeOpenAIClient()
    provider = OpenAIProvider(api_key="test", model="test-model", client=client)
    result = provider.run(system="sys", history=[ChatTurn("user", "filial?")], tool_specs=TOOL_SPECS, execute=lambda n, a: {"ok": True, "branches": []})
    assert result.text == "Filiallar: Markaz." and result.output_tokens == 16
    assert client.calls[1]["messages"][-1]["role"] == "tool"


def test_provider_requires_key_and_model():
    with pytest.raises(AIProviderError):
        AnthropicProvider(api_key="", model="x", client=object())
    with pytest.raises(AIProviderError):
        OpenAIProvider(api_key="k", model="", client=object())
