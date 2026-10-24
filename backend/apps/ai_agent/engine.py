"""AI agent ishga tushirish: provider tanlash, tarix, tool'lar, guard'lar, limit va log."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import timedelta

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone

from apps.ai_agent.guards import apply_output_guards
from apps.ai_agent.models import AICallLog
from apps.ai_agent.prompts import build_system_prompt
from apps.ai_agent.providers.base import AIProviderError, ChatTurn
from apps.ai_agent.services import get_ai_settings
from apps.ai_agent.tools import TOOL_SPECS, ToolContext, ToolExecutor

logger = logging.getLogger(__name__)


class BudgetExceeded(AIProviderError):
    def __init__(self):
        super().__init__("budget_exceeded")


@dataclass
class AgentReply:
    text: str
    is_demo: bool
    sources: list = field(default_factory=list)
    tool_trace: list = field(default_factory=list)
    handoff_requested: bool = False
    guard_flags: list = field(default_factory=list)


def get_chat_provider(name: str | None = None):
    name = (name or settings.AI_PROVIDER).lower()
    if name == "anthropic":
        from apps.ai_agent.providers.anthropic_provider import AnthropicProvider

        return AnthropicProvider()
    if name == "openai":
        from apps.ai_agent.providers.openai_provider import OpenAIProvider

        return OpenAIProvider()
    raise AIProviderError("not_configured", f"Noma'lum AI_PROVIDER: {name}")


def build_history(conversation, current_message, limit: int | None = None) -> list[ChatTurn]:
    from apps.conversations.models import Message

    limit = limit or settings.AI_HISTORY_MESSAGES
    qs = Message.objects.filter(conversation=conversation, id__lt=current_message.id).exclude(kind=Message.Kind.EVENT).order_by("-created_at", "-id")[:limit]
    turns = []
    for m in reversed(list(qs)):
        if m.sender == Message.Sender.CUSTOMER:
            turns.append(ChatTurn("user", m.text))
        elif m.sender in (Message.Sender.AI, Message.Sender.OPERATOR):
            prefix = "[Administrator] " if m.sender == Message.Sender.OPERATOR else ""
            turns.append(ChatTurn("assistant", prefix + m.text))
    turns.append(ChatTurn("user", current_message.text))
    return turns


def tokens_used_today(conversation) -> int:
    since = timezone.now() - timedelta(hours=24)
    agg = AICallLog.objects.filter(conversation=conversation, created_at__gte=since).aggregate(i=Sum("input_tokens"), o=Sum("output_tokens"))
    return int(agg["i"] or 0) + int(agg["o"] or 0)


class AgentRunner:
    def __init__(self, conversation, customer_message, *, now=None, provider=None):
        self.conversation = conversation
        self.customer_message = customer_message
        self.now = now
        self.provider_override = provider
        self.pending_logs: list[AICallLog] = []
        self.ai_settings = get_ai_settings(conversation.organization)
        self.executor = ToolExecutor(ToolContext(conversation=conversation, customer_message=customer_message, dry_run=conversation.channel == "test", now=now))

    def _log(self, provider: str, status: str, *, model: str = "", input_tokens=0, output_tokens=0, latency_ms=0, error_code=""):
        """Loglar xotirada yig'iladi va flush_logs() bilan yoziladi (savepoint rollback'dan keyin ham saqlanishi uchun)."""

        self.pending_logs.append(
            AICallLog(
                organization=self.conversation.organization,
                conversation=self.conversation,
                provider=provider,
                model=(model or "")[:128],
                status=status,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
                error_code=(error_code or "")[:64],
            )
        )

    def flush_logs(self) -> None:
        if self.pending_logs:
            AICallLog.objects.bulk_create(self.pending_logs)
            self.pending_logs = []

    def respond(self) -> AgentReply:
        provider_name = "custom" if self.provider_override else settings.AI_PROVIDER
        started = time.monotonic()
        if provider_name == "demo":
            from apps.ai_agent.providers.demo import DemoAgent

            text = DemoAgent(self.executor, self.ai_settings).respond(self.customer_message.text)
            self._log("demo", AICallLog.Status.OK, model="deterministic-demo", latency_ms=int((time.monotonic() - started) * 1000))
            self.flush_logs()
            return AgentReply(
                text=text,
                is_demo=True,
                sources=self.executor.sources,
                tool_trace=self.executor.trace,
                handoff_requested=self.executor.handoff_requested,
            )

        if tokens_used_today(self.conversation) >= settings.AI_DAILY_TOKEN_BUDGET_PER_CONVERSATION:
            self._log(provider_name, AICallLog.Status.BUDGET, error_code="budget_exceeded")
            raise BudgetExceeded()

        try:
            provider = self.provider_override or get_chat_provider(provider_name)
            result = provider.run(
                system=build_system_prompt(self.conversation, self.ai_settings, now=self.now),
                history=build_history(self.conversation, self.customer_message),
                tool_specs=TOOL_SPECS,
                execute=self.executor.execute,
            )
        except AIProviderError as exc:
            status = AICallLog.Status.TIMEOUT if exc.code == "timeout" else AICallLog.Status.ERROR
            self._log(provider_name, status, model=settings.AI_MODEL, latency_ms=int((time.monotonic() - started) * 1000), error_code=exc.code)
            logger.warning("AI provider xatosi (%s): %s", provider_name, exc.code)
            raise
        except Exception as exc:  # noqa: BLE001
            self._log(provider_name, AICallLog.Status.ERROR, model=settings.AI_MODEL, error_code=exc.__class__.__name__)
            logger.exception("AI agentda kutilmagan xato")
            raise AIProviderError("unexpected") from exc

        text, flags = apply_output_guards(result.text, self.executor, self.conversation.language)
        self._log(
            provider_name,
            AICallLog.Status.OK,
            model=result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=int((time.monotonic() - started) * 1000),
        )
        self.flush_logs()
        if flags:
            logger.info("AI javobi guard tomonidan almashtirildi: %s", ",".join(flags))
        return AgentReply(
            text=text,
            is_demo=False,
            sources=self.executor.sources,
            tool_trace=self.executor.trace,
            handoff_requested=self.executor.handoff_requested,
            guard_flags=flags,
        )
