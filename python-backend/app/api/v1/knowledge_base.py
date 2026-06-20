from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin_user
from app.core.responses import ApiResponse, success
from app.db.session import get_db_session
from app.models import User
from app.rag.retrieve import VectorSpaceManager, create_vector_space_manager
from app.schemas.knowledge import (
    ChunkStrategyOption,
    DeleteResponse,
    KnowledgeBaseCreateRequest,
    KnowledgeBasePageResponse,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdateRequest,
)
from app.services.knowledge_service import KnowledgeService

router = APIRouter(prefix="/knowledge-base", tags=["knowledge-base"])


def get_vector_space_manager() -> VectorSpaceManager:
    return create_vector_space_manager()


def get_knowledge_service(
    session: AsyncSession = Depends(get_db_session),
    vector_space_manager: VectorSpaceManager = Depends(get_vector_space_manager),
) -> KnowledgeService:
    return KnowledgeService(session, vector_space_manager)


@router.get("", response_model=ApiResponse[KnowledgeBasePageResponse])
async def list_knowledge_bases_api(
    current: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=200),
    name: str | None = None,
    _: User = Depends(require_admin_user),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> ApiResponse[KnowledgeBasePageResponse]:
    return success(await service.list_knowledge_bases(current=current, size=size, name=name))


@router.get("/chunk-strategies", response_model=ApiResponse[list[ChunkStrategyOption]])
async def list_chunk_strategies_api(
    _: User = Depends(require_admin_user),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> ApiResponse[list[ChunkStrategyOption]]:
    return success(await service.list_chunk_strategies())


@router.get("/{kb_id}", response_model=ApiResponse[KnowledgeBaseResponse])
async def get_knowledge_base_api(
    kb_id: str,
    _: User = Depends(require_admin_user),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> ApiResponse[KnowledgeBaseResponse]:
    return success(await service.get_knowledge_base(kb_id))


@router.post("", response_model=ApiResponse[str])
async def create_knowledge_base_api(
    request: KnowledgeBaseCreateRequest,
    user: User = Depends(require_admin_user),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> ApiResponse[str]:
    created = await service.create_knowledge_base(request, str(user.id))
    return success(created.id)


@router.put("/{kb_id}", response_model=ApiResponse[None])
async def update_knowledge_base_api(
    kb_id: str,
    request: KnowledgeBaseUpdateRequest,
    user: User = Depends(require_admin_user),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> ApiResponse[None]:
    await service.update_knowledge_base(kb_id, request, str(user.id))
    return success()


@router.delete("/{kb_id}", response_model=ApiResponse[DeleteResponse])
async def delete_knowledge_base_api(
    kb_id: str,
    user: User = Depends(require_admin_user),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> ApiResponse[DeleteResponse]:
    return success(await service.delete_knowledge_base(kb_id, str(user.id)))
