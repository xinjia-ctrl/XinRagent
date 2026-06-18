from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin_user
from app.core.responses import ApiResponse, success
from app.db.session import get_db_session
from app.models import User
from app.schemas.document import (
    KnowledgeChunkBatchEnableRequest,
    KnowledgeChunkCreateRequest,
    KnowledgeChunkPageResponse,
    KnowledgeChunkResponse,
    KnowledgeChunkUpdateRequest,
    KnowledgeDocumentChunkLogPageResponse,
    KnowledgeDocumentPageResponse,
    KnowledgeDocumentResponse,
    KnowledgeDocumentSearchItem,
    KnowledgeDocumentUpdateRequest,
)
from app.services.document_service import DocumentService

router = APIRouter(prefix="/knowledge-base", tags=["documents"])


def get_document_service(session: AsyncSession = Depends(get_db_session)) -> DocumentService:
    return DocumentService(session)


@router.get("/{kb_id}/docs", response_model=ApiResponse[KnowledgeDocumentPageResponse])
async def list_documents_api(
    kb_id: str,
    current: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=200),
    status: str | None = None,
    keyword: str | None = None,
    _: User = Depends(require_admin_user),
    service: DocumentService = Depends(get_document_service),
) -> ApiResponse[KnowledgeDocumentPageResponse]:
    return success(await service.list_documents(kb_id, current=current, size=size, status=status, keyword=keyword))


@router.get("/docs/search", response_model=ApiResponse[list[KnowledgeDocumentSearchItem]])
async def search_documents_api(
    keyword: str = "",
    limit: int = Query(default=8, ge=1, le=50),
    _: User = Depends(require_admin_user),
    service: DocumentService = Depends(get_document_service),
) -> ApiResponse[list[KnowledgeDocumentSearchItem]]:
    return success(await service.search_documents(keyword, limit=limit))


@router.get("/docs/{doc_id}", response_model=ApiResponse[KnowledgeDocumentResponse])
async def get_document_api(
    doc_id: str,
    _: User = Depends(require_admin_user),
    service: DocumentService = Depends(get_document_service),
) -> ApiResponse[KnowledgeDocumentResponse]:
    return success(await service.get_document(doc_id))


@router.put("/docs/{doc_id}", response_model=ApiResponse[None])
async def update_document_api(
    doc_id: str,
    request: KnowledgeDocumentUpdateRequest,
    user: User = Depends(require_admin_user),
    service: DocumentService = Depends(get_document_service),
) -> ApiResponse[None]:
    await service.update_document(doc_id, request, str(user.id))
    return success()


@router.post("/docs/{doc_id}/chunk", response_model=ApiResponse[None])
async def start_document_chunk_api(
    doc_id: str,
    user: User = Depends(require_admin_user),
    service: DocumentService = Depends(get_document_service),
) -> ApiResponse[None]:
    await service.start_document_chunk(doc_id, str(user.id))
    return success()


@router.patch("/docs/{doc_id}/enable", response_model=ApiResponse[None])
async def enable_document_api(
    doc_id: str,
    value: bool = Query(default=True),
    user: User = Depends(require_admin_user),
    service: DocumentService = Depends(get_document_service),
) -> ApiResponse[None]:
    await service.enable_document(doc_id, value, str(user.id))
    return success()


@router.delete("/docs/{doc_id}", response_model=ApiResponse[None])
async def delete_document_api(
    doc_id: str,
    user: User = Depends(require_admin_user),
    service: DocumentService = Depends(get_document_service),
) -> ApiResponse[None]:
    await service.delete_document(doc_id, str(user.id))
    return success()


@router.get("/docs/{doc_id}/chunks", response_model=ApiResponse[KnowledgeChunkPageResponse])
async def list_chunks_api(
    doc_id: str,
    current: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=200),
    enabled: int | None = Query(default=None, ge=0, le=1),
    _: User = Depends(require_admin_user),
    service: DocumentService = Depends(get_document_service),
) -> ApiResponse[KnowledgeChunkPageResponse]:
    return success(await service.list_chunks(doc_id, current=current, size=size, enabled=enabled))


@router.post("/docs/{doc_id}/chunks", response_model=ApiResponse[KnowledgeChunkResponse])
async def create_chunk_api(
    doc_id: str,
    request: KnowledgeChunkCreateRequest,
    user: User = Depends(require_admin_user),
    service: DocumentService = Depends(get_document_service),
) -> ApiResponse[KnowledgeChunkResponse]:
    return success(await service.create_chunk(doc_id, request, str(user.id)))


@router.put("/docs/{doc_id}/chunks/{chunk_id}", response_model=ApiResponse[None])
async def update_chunk_api(
    doc_id: str,
    chunk_id: str,
    request: KnowledgeChunkUpdateRequest,
    user: User = Depends(require_admin_user),
    service: DocumentService = Depends(get_document_service),
) -> ApiResponse[None]:
    await service.update_chunk(doc_id, chunk_id, request, str(user.id))
    return success()


@router.delete("/docs/{doc_id}/chunks/{chunk_id}", response_model=ApiResponse[None])
async def delete_chunk_api(
    doc_id: str,
    chunk_id: str,
    user: User = Depends(require_admin_user),
    service: DocumentService = Depends(get_document_service),
) -> ApiResponse[None]:
    await service.delete_chunk(doc_id, chunk_id, str(user.id))
    return success()


@router.patch("/docs/{doc_id}/chunks/{chunk_id}/enable", response_model=ApiResponse[None])
async def enable_chunk_api(
    doc_id: str,
    chunk_id: str,
    value: bool = Query(default=True),
    user: User = Depends(require_admin_user),
    service: DocumentService = Depends(get_document_service),
) -> ApiResponse[None]:
    await service.enable_chunk(doc_id, chunk_id, value, str(user.id))
    return success()


@router.patch("/docs/{doc_id}/chunks/batch-enable", response_model=ApiResponse[None])
async def batch_enable_chunks_api(
    doc_id: str,
    request: KnowledgeChunkBatchEnableRequest,
    value: bool = Query(default=True),
    user: User = Depends(require_admin_user),
    service: DocumentService = Depends(get_document_service),
) -> ApiResponse[None]:
    await service.batch_enable_chunks(doc_id, request, value, str(user.id))
    return success()


@router.get("/docs/{doc_id}/chunk-logs", response_model=ApiResponse[KnowledgeDocumentChunkLogPageResponse])
async def list_chunk_logs_api(
    doc_id: str,
    current: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=200),
    _: User = Depends(require_admin_user),
    service: DocumentService = Depends(get_document_service),
) -> ApiResponse[KnowledgeDocumentChunkLogPageResponse]:
    return success(await service.list_chunk_logs(doc_id, current=current, size=size))
