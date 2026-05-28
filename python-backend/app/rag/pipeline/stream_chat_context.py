from dataclasses import dataclass


@dataclass(frozen=True)
class StreamChatContext:
    question: str
    conversation_id: str | None
    task_id: str
    user_id: str | None = None
    deep_thinking: bool = False
