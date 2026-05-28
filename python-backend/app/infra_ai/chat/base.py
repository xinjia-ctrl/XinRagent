from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


@dataclass(frozen=True)
class ChatRequest:
    messages: Sequence[ChatMessage]
    model: str
    temperature: float = 0.7
    stream: bool = False
    extra_body: dict | None = None


@dataclass(frozen=True)
class ChatResponse:
    content: str
    model: str
    raw: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ChatChunk:
    delta: str
    finish_reason: str | None = None
    raw: dict = field(default_factory=dict)


class ChatClient(Protocol):
    async def complete(self, request: ChatRequest) -> ChatResponse:
        ...

    def stream(self, request: ChatRequest) -> AsyncIterator[ChatChunk]:
        ...
