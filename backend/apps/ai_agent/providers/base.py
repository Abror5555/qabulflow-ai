from __future__ import annotations

from dataclasses import dataclass, field


class AIProviderError(Exception):
    """Provider xatosi. code — log va statistikada ko'rinadigan qisqa kod (maxfiy ma'lumotsiz)."""

    def __init__(self, code: str, message: str = ""):
        super().__init__(message or code)
        self.code = code


@dataclass
class ProviderResult:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    iterations: int = 0
    tool_calls: list = field(default_factory=list)


@dataclass
class ChatTurn:
    role: str  # "user" | "assistant"
    text: str


def merge_turns(turns: list[ChatTurn]) -> list[ChatTurn]:
    """Ketma-ket bir xil rolli xabarlarni birlashtiradi va user bilan boshlanishini ta'minlaydi."""

    merged: list[ChatTurn] = []
    for turn in turns:
        if not turn.text.strip():
            continue
        if merged and merged[-1].role == turn.role:
            merged[-1] = ChatTurn(turn.role, merged[-1].text + "\n" + turn.text)
        else:
            merged.append(ChatTurn(turn.role, turn.text))
    while merged and merged[0].role != "user":
        merged.pop(0)
    return merged
