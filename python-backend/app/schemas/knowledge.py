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
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    embeddingModel: str = Field(validation_alias=AliasChoices("embedding_model", "embeddingModel"))
    collectionName: str = Field(validation_alias=AliasChoices("collection_name", "collectionName"))
    createdBy: str | None = Field(default=None, validation_alias=AliasChoices("created_by", "createdBy"))
    documentCount: int = Field(default=0, validation_alias=AliasChoices("document_count", "documentCount"))
    createTime: datetime | None = Field(default=None, validation_alias=AliasChoices("create_time", "createTime"))
    updateTime: datetime | None = Field(default=None, validation_alias=AliasChoices("update_time", "updateTime"))


class KnowledgeBasePageResponse(BaseModel):
    records: list[KnowledgeBaseResponse]
    total: int
    size: int
    current: int
    pages: int


class DeleteResponse(BaseModel):
    deleted: bool


class ChunkStrategyOption(BaseModel):
    value: str
    label: str
    defaultConfig: dict[str, int]
