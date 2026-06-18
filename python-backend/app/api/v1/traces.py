from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin_user
from app.core.responses import ApiResponse, success
from app.db.session import get_db_session
from app.models import User
from app.schemas.trace import TraceDetailResponse, TraceNodeResponse, TraceRunPageResponse
from app.services.trace_service import TraceService

router = APIRouter(prefix="/rag/traces", tags=["trace"])


def get_trace_service(session: AsyncSession = Depends(get_db_session)) -> TraceService:
    return TraceService(session)


@router.get("/runs", response_model=ApiResponse[TraceRunPageResponse])
async def list_trace_runs_api(
    current: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=200),
    traceId: str | None = None,
    conversationId: str | None = None,
    taskId: str | None = None,
    status: str | None = None,
    _: User = Depends(require_admin_user),
    service: TraceService = Depends(get_trace_service),
) -> ApiResponse[TraceRunPageResponse]:
    return success(
        await service.list_runs(
            current=current,
            size=size,
            trace_id=traceId,
            conversation_id=conversationId,
            task_id=taskId,
            status=status,
        ),
    )


@router.get("/runs/{trace_id}", response_model=ApiResponse[TraceDetailResponse])
async def get_trace_run_api(
    trace_id: str,
    _: User = Depends(require_admin_user),
    service: TraceService = Depends(get_trace_service),
) -> ApiResponse[TraceDetailResponse]:
    return success(await service.get_run_detail(trace_id))


@router.get("/runs/{trace_id}/nodes", response_model=ApiResponse[list[TraceNodeResponse]])
async def list_trace_nodes_api(
    trace_id: str,
    _: User = Depends(require_admin_user),
    service: TraceService = Depends(get_trace_service),
) -> ApiResponse[list[TraceNodeResponse]]:
    return success(await service.list_nodes(trace_id))
