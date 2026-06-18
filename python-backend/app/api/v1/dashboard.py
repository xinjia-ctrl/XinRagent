from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin_user
from app.core.responses import ApiResponse, success
from app.db.session import get_db_session
from app.models import User
from app.schemas.dashboard import (
    DashboardOverviewResponse,
    DashboardPerformanceResponse,
    DashboardTrendsResponse,
)
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/admin/dashboard", tags=["dashboard"])


def get_dashboard_service(session: AsyncSession = Depends(get_db_session)) -> DashboardService:
    return DashboardService(session)


@router.get("/overview", response_model=ApiResponse[DashboardOverviewResponse])
async def get_dashboard_overview_api(
    window: str = "24h",
    _: User = Depends(require_admin_user),
    service: DashboardService = Depends(get_dashboard_service),
) -> ApiResponse[DashboardOverviewResponse]:
    return success(await service.get_overview(window=window))


@router.get("/performance", response_model=ApiResponse[DashboardPerformanceResponse])
async def get_dashboard_performance_api(
    window: str = "24h",
    _: User = Depends(require_admin_user),
    service: DashboardService = Depends(get_dashboard_service),
) -> ApiResponse[DashboardPerformanceResponse]:
    return success(await service.get_performance(window=window))


@router.get("/trends", response_model=ApiResponse[DashboardTrendsResponse])
async def get_dashboard_trends_api(
    metric: str,
    window: str = "7d",
    granularity: str = "day",
    _: User = Depends(require_admin_user),
    service: DashboardService = Depends(get_dashboard_service),
) -> ApiResponse[DashboardTrendsResponse]:
    return success(await service.get_trends(metric=metric, window=window, granularity=granularity))
