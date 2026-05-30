from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.responses import ApiResponse, success
from app.db.session import get_db_session
from app.models import User
from app.schemas.trace import TraceDetailResponse, TraceRunResponse
from app.services.trace_service import TraceService

router = APIRouter(prefix="/rag/traces", tags=["trace"])


def get_trace_service(session: AsyncSession = Depends(get_db_session)) -> TraceService:
    return TraceService(session)


@router.get("/runs", response_model=ApiResponse[list[TraceRunResponse]])
async def list_trace_runs_api(
    _: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    service: TraceService = Depends(get_trace_service),
) -> ApiResponse[list[TraceRunResponse]]:
    return success(await service.list_runs(limit=limit))


@router.get("/runs/{trace_id}", response_model=ApiResponse[TraceDetailResponse])
async def get_trace_run_api(
    trace_id: str,
    _: User = Depends(get_current_user),
    service: TraceService = Depends(get_trace_service),
) -> ApiResponse[TraceDetailResponse]:
    return success(await service.get_run_detail(trace_id))
