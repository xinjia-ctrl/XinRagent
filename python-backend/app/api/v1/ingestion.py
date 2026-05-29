from fastapi import APIRouter, Depends, File, UploadFile

from app.api.deps import get_current_user
from app.core.responses import ApiResponse, success
from app.ingestion.storage import LocalFileStorage
from app.models import User
from app.schemas.ingestion import UploadedDocumentResponse

router = APIRouter(prefix="/knowledge-base", tags=["ingestion"])


def get_file_storage() -> LocalFileStorage:
    return LocalFileStorage()


@router.post("/{kb_id}/docs/upload", response_model=ApiResponse[UploadedDocumentResponse])
async def upload_document_api(
    kb_id: str,
    file: UploadFile = File(...),
    _: User = Depends(get_current_user),
    storage: LocalFileStorage = Depends(get_file_storage),
) -> ApiResponse[UploadedDocumentResponse]:
    stored_file = await storage.save_upload(kb_id, file)
    return success(
        UploadedDocumentResponse(
            kb_id=kb_id,
            doc_id=stored_file.file_id,
            file_name=stored_file.original_name,
            file_type=stored_file.file_type,
            file_size=stored_file.file_size,
            storage_path=str(stored_file.path),
        ),
    )
