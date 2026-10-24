"""OpenAI Chat Completions API (rasmiy `openai` Python SDK) orqali function-calling agent sikli."""

from __future__ import annotations

import json

from django.conf import settings

from apps.ai_agent.providers.base import AIProviderError, ChatTurn, ProviderResult, merge_turns


class OpenAIProvider:
    name = "openai"

    def __init__(self, *, api_key: str | None = None, model: str | None = None, client=None):
        self.api_key = api_key if api_key is not None else settings.OPENAI_API_KEY
        self.model = model if model is not None else settings.AI_MODEL
        if not self.api_key:
            raise AIProviderError("not_configured", "OPENAI_API_KEY kiritilmagan")
        if not self.model:
            raise AIProviderError("not_configured", "AI_MODEL kiritilmagan")
        if client is None:
            import openai

            client = openai.OpenAI(api_key=self.api_key, timeout=settings.AI_TIMEOUT_SECONDS, max_retries=settings.AI_MAX_RETRIES)
        self.client = client

    @staticmethod
    def _tool_specs(specs: list[dict]) -> list[dict]:
        return [{"type": "function", "function": {"name": s["name"], "description": s["description"], "parameters": s["input_schema"]}} for s in specs]

    def run(self, *, system: str, history: list[ChatTurn], tool_specs: list[dict], execute) -> ProviderResult:
        try:
            import openai
        except ImportError as exc:  # pragma: no cover
            raise AIProviderError("sdk_missing") from exc

        messages: list[dict] = [{"role": "system", "content": system}]
        messages += [{"role": t.role, "content": t.text} for t in merge_turns(history)]
        result = ProviderResult(text="", model=self.model)
        tools = self._tool_specs(tool_specs)
        for iteration in range(settings.AI_MAX_TOOL_ITERATIONS):
            result.iterations = iteration + 1
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tools,
                    max_completion_tokens=settings.AI_MAX_OUTPUT_TOKENS,
                )
            except openai.APITimeoutError as exc:
                raise AIProviderError("timeout") from exc
            except openai.RateLimitError as exc:
                raise AIProviderError("rate_limited") from exc
            except openai.AuthenticationError as exc:
                raise AIProviderError("auth_failed") from exc
            except openai.APIStatusError as exc:
                raise AIProviderError(f"http_{getattr(exc, 'status_code', 'error')}") from exc
            except openai.APIConnectionError as exc:
                raise AIProviderError("connection_error") from exc

            usage = getattr(response, "usage", None)
            if usage is not None:
                result.input_tokens += int(getattr(usage, "prompt_tokens", 0) or 0)
                result.output_tokens += int(getattr(usage, "completion_tokens", 0) or 0)
            choice = response.choices[0]
            message = choice.message
            tool_calls = list(getattr(message, "tool_calls", None) or [])
            if tool_calls:
                messages.append(
                    {
                        "role": "assistant",
                        "content": message.content or "",
                        "tool_calls": [
                            {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}} for tc in tool_calls
                        ],
                    }
                )
                for tc in tool_calls:
                    try:
                        args = json.loads(tc.function.arguments or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    output = execute(tc.function.name, args if isinstance(args, dict) else {})
                    result.tool_calls.append(tc.function.name)
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(output, ensure_ascii=False, default=str)})
                continue
            result.text = (message.content or "").strip()
            if not result.text:
                raise AIProviderError("empty_response")
            return result
        raise AIProviderError("tool_loop_limit")
