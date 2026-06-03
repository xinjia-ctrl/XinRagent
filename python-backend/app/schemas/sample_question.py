from datetime import datetime

from pydantic import BaseModel, Field


class SampleQuestionResponse(BaseModel):
    id: str
    title: str | None = None
    description: str | None = None
    question: str
    createTime: datetime | None = Field(default=None)
    updateTime: datetime | None = Field(default=None)


class SampleQuestionPageResponse(BaseModel):
    records: list[SampleQuestionResponse]
    total: int
    size: int
    current: int
    pages: int


class SampleQuestionPayload(BaseModel):
    title: str | None = None
    description: str | None = None
    question: str | None = None
