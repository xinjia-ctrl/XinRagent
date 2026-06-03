from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.responses import ApiResponse, success
from app.db.session import get_db_session
from app.models import User
from app.schemas.intent_tree import (
    IntentNodeBatchRequest,
    IntentNodeCreateRequest,
    IntentNodeTreeResponse,
    IntentNodeUpdateRequest,
)
from app.services.intent_tree_service import IntentTreeService

router = APIRouter(prefix="/intent-tree", tags=["intent-tree"])


def get_intent_tree_service(session: AsyncSession = Depends(get_db_session)) -> IntentTreeService:
    return IntentTreeService(session)


@router.get("/trees", response_model=ApiResponse[list[IntentNodeTreeResponse]])
async def list_intent_tree_api(
    _: User = Depends(get_current_user),
    service: IntentTreeService = Depends(get_intent_tree_service),
) -> ApiResponse[list[IntentNodeTreeResponse]]:
    return success(await service.list_tree())


@router.post("", response_model=ApiResponse[str])
async def create_intent_node_api(
    request: IntentNodeCreateRequest,
    user: User = Depends(get_current_user),
    service: IntentTreeService = Depends(get_intent_tree_service),
) -> ApiResponse[str]:
    return success(await service.create_node(request, str(user.id)))


@router.put("/{node_id}", response_model=ApiResponse[None])
async def update_intent_node_api(
    node_id: str,
    request: IntentNodeUpdateRequest,
    user: User = Depends(get_current_user),
    service: IntentTreeService = Depends(get_intent_tree_service),
) -> ApiResponse[None]:
    await service.update_node(node_id, request, str(user.id))
    return success()


@router.delete("/{node_id}", response_model=ApiResponse[None])
async def delete_intent_node_api(
    node_id: str,
    user: User = Depends(get_current_user),
    service: IntentTreeService = Depends(get_intent_tree_service),
) -> ApiResponse[None]:
    await service.delete_node(node_id, str(user.id))
    return success()


@router.post("/batch/enable", response_model=ApiResponse[None])
async def batch_enable_intent_nodes_api(
    request: IntentNodeBatchRequest,
    user: User = Depends(get_current_user),
    service: IntentTreeService = Depends(get_intent_tree_service),
) -> ApiResponse[None]:
    await service.batch_enable(request, enabled=1, user_id=str(user.id))
    return success()


@router.post("/batch/disable", response_model=ApiResponse[None])
async def batch_disable_intent_nodes_api(
    request: IntentNodeBatchRequest,
    user: User = Depends(get_current_user),
    service: IntentTreeService = Depends(get_intent_tree_service),
) -> ApiResponse[None]:
    await service.batch_enable(request, enabled=0, user_id=str(user.id))
    return success()


@router.post("/batch/delete", response_model=ApiResponse[None])
async def batch_delete_intent_nodes_api(
    request: IntentNodeBatchRequest,
    user: User = Depends(get_current_user),
    service: IntentTreeService = Depends(get_intent_tree_service),
) -> ApiResponse[None]:
    await service.batch_delete(request, str(user.id))
    return success()
