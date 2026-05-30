from pydantic import BaseModel


class KnowledgeDocumentResponse(BaseModel):
    id: str
    kb_id: str
    doc_name: str
    file_url: str
    file_type: str
    file_size: int | None = None
    status: str
    chunk_count: int = 0


class KnowledgeChunkResponse(BaseModel):
    id: str
    kb_id: str
    doc_id: str
    chunk_index: int
    content: str
    char_count: int | None = None
    token_count: int | None = None
