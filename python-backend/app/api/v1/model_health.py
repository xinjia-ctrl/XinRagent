from fastapi import APIRouter, Depends

from app.api.deps import require_admin_user
from app.api.v1.chat import get_llm_service
from app.core.responses import ApiResponse, success
from app.infra_ai.chat import RoutingLLMService
from app.models import User
from app.schemas.model_health import ModelHealthItem, ModelProbeResult

router = APIRouter(prefix="/admin/ai", tags=["ai-observability"])


@router.get("/model-health", response_model=ApiResponse[list[ModelHealthItem]])
async def get_model_health_api(
    _: User = Depends(require_admin_user),
    llm_service: RoutingLLMService = Depends(get_llm_service),
) -> ApiResponse[list[ModelHealthItem]]:
    return success([ModelHealthItem(**item) for item in llm_service.health_snapshot()])


@router.post("/model-health/probe", response_model=ApiResponse[list[ModelProbeResult]])
async def probe_model_health_api(
    _: User = Depends(require_admin_user),
    llm_service: RoutingLLMService = Depends(get_llm_service),
) -> ApiResponse[list[ModelProbeResult]]:
    return success([ModelProbeResult(**item) for item in await llm_service.probe_first_token()])
