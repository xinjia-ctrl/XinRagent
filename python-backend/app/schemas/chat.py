from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class ChatQuery(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    question: str
    conversation_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("conversation_id", "conversationId"),
    )
    deep_thinking: bool = Field(
        default=False,
        validation_alias=AliasChoices("deep_thinking", "deepThinking"),
    )


class StopChatRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    task_id: str = Field(validation_alias=AliasChoices("task_id", "taskId"))


class StopChatResponse(BaseModel):
    stopped: bool
