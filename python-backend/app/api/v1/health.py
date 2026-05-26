from fastapi import APIRouter

from app.schemas.common import HealthCheck

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthCheck)
async def health_check() -> HealthCheck:
    return HealthCheck(status="ok")
