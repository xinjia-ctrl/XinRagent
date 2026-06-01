from datetime import datetime

from pydantic import BaseModel, Field


class ConversationUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=128)


class ConversationResponse(BaseModel):
    conversationId: str
    title: str
    lastTime: datetime | None = None


class ConversationMessageResponse(BaseModel):
    id: str
    conversationId: str
    role: str
    content: str
    thinkingContent: str | None = None
    thinkingDuration: int | None = None
    vote: int | None = None
    createTime: datetime | None = None


class MessageFeedbackRequest(BaseModel):
    vote: int = Field(ge=-1, le=1)
