from pydantic import BaseModel


class UploadedDocumentResponse(BaseModel):
    kb_id: str
    doc_id: str
    file_name: str
    file_type: str
    file_size: int
    storage_path: str
    status: str = "uploaded"
