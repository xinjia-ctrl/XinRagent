from pydantic import BaseModel, Field


class KnowledgeBaseCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    embedding_model: str = "qwen-emb-8b"
    collection_name: str | None = None


class KnowledgeBaseUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    embedding_model: str | None = None
    collection_name: str | None = None


class KnowledgeBaseResponse(BaseModel):
    id: str
    name: str
    embedding_model: str
    collection_name: str
    created_by: str


class DeleteResponse(BaseModel):
    deleted: bool
