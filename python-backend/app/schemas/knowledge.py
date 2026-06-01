from datetime import datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class KnowledgeBaseCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(min_length=1, max_length=128)
    embedding_model: str = Field(
        default="qwen-emb-8b",
        validation_alias=AliasChoices("embedding_model", "embeddingModel"),
    )
    collection_name: str | None = Field(
        default=None,
        validation_alias=AliasChoices("collection_name", "collectionName"),
    )


class KnowledgeBaseUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str | None = Field(default=None, min_length=1, max_length=128)
    embedding_model: str | None = Field(
        default=None,
        validation_alias=AliasChoices("embedding_model", "embeddingModel"),
    )
    collection_name: str | None = Field(
        default=None,
        validation_alias=AliasChoices("collection_name", "collectionName"),
    )


class KnowledgeBaseResponse(BaseModel):
    id: str
    name: str
    embeddingModel: str
    collectionName: str
    createdBy: str | None = None
    documentCount: int = 0
    createTime: datetime | None = None
    updateTime: datetime | None = None


class KnowledgeBasePageResponse(BaseModel):
    records: list[KnowledgeBaseResponse]
    total: int
    size: int
    current: int
    pages: int


class DeleteResponse(BaseModel):
    deleted: bool
