"""Anthropic Messages API (rasmiy `anthropic` Python SDK) orqali tool-use agent sikli."""

from __future__ import annotations

import json

from django.conf import settings

from apps.ai_agent.providers.base import AIProviderError, ChatTurn, ProviderResult, merge_turns


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, *, api_key: str | None = None, model: str | None = None, client=None):
        self.api_key = api_key if api_key is not None else settings.ANTHROPIC_API_KEY
        self.model = model if model is not None else settings.AI_MODEL
        if not self.api_key:
            raise AIProviderError("not_configured", "ANTHROPIC_API_KEY kiritilmagan")
        if not self.model:
            raise AIProviderError("not_configured", "AI_MODEL kiritilmagan")
        if client is None:
            import anthropic

            client = anthropic.Anthropic(api_key=self.api_key, timeout=settings.AI_TIMEOUT_SECONDS, max_retries=settings.AI_MAX_RETRIES)
        self.client = client

    @staticmethod
    def _tool_specs(specs: list[dict]) -> list[dict]:
        return [{"name": s["name"], "description": s["description"], "input_schema": s["input_schema"]} for s in specs]

    def run(self, *, system: str, history: list[ChatTurn], tool_specs: list[dict], execute) -> ProviderResult:
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover
            raise AIProviderError("sdk_missing") from exc

        messages = [{"role": t.role, "content": t.text} for t in merge_turns(history)]
        if not messages:
            raise AIProviderError("empty_history")
        result = ProviderResult(text="", model=self.model)
        tools = self._tool_specs(tool_specs)
        for iteration in range(settings.AI_MAX_TOOL_ITERATIONS):
            result.iterations = iteration + 1
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=settings.AI_MAX_OUTPUT_TOKENS,
                    system=system,
                    messages=messages,
                    tools=tools,
                )
            except anthropic.APITimeoutError as exc:
                raise AIProviderError("timeout") from exc
            except anthropic.RateLimitError as exc:
                raise AIProviderError("rate_limited") from exc
            except anthropic.AuthenticationError as exc:
                raise AIProviderError("auth_failed") from exc
            except anthropic.APIStatusError as exc:
                raise AIProviderError(f"http_{getattr(exc, 'status_code', 'error')}") from exc
            except anthropic.APIConnectionError as exc:
                raise AIProviderError("connection_error") from exc

            usage = getattr(response, "usage", None)
            if usage is not None:
                result.input_tokens += int(getattr(usage, "input_tokens", 0) or 0)
                result.output_tokens += int(getattr(usage, "output_tokens", 0) or 0)

            blocks = list(getattr(response, "content", []) or [])
            text_parts = [b.text for b in blocks if getattr(b, "type", "") == "text"]
            tool_uses = [b for b in blocks if getattr(b, "type", "") == "tool_use"]

            if getattr(response, "stop_reason", "") == "tool_use" and tool_uses:
                assistant_content = []
                for b in blocks:
                    if b.type == "text":
                        assistant_content.append({"type": "text", "text": b.text})
                    elif b.type == "tool_use":
                        assistant_content.append({"type": "tool_use", "id": b.id, "name": b.name, "input": b.input})
                messages.append({"role": "assistant", "content": assistant_content})
                tool_results = []
                for b in tool_uses:
                    output = execute(b.name, b.input if isinstance(b.input, dict) else {})
                    result.tool_calls.append(b.name)
                    tool_results.append({"type": "tool_result", "tool_use_id": b.id, "content": json.dumps(output, ensure_ascii=False, default=str)})
                messages.append({"role": "user", "content": tool_results})
                continue

            result.text = "\n".join(p for p in text_parts if p).strip()
            if not result.text:
                raise AIProviderError("empty_response")
            return result
        raise AIProviderError("tool_loop_limit")
