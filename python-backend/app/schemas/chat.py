from pydantic import BaseModel


class ChatQuery(BaseModel):
    question: str
    conversation_id: str | None = None
    deep_thinking: bool = False


class StopChatRequest(BaseModel):
    task_id: str


class StopChatResponse(BaseModel):
    stopped: bool
