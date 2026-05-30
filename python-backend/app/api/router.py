from fastapi import APIRouter

from app.api.v1 import auth, chat, health, ingestion, knowledge_base, users
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router, prefix=settings.api_prefix)
api_router.include_router(users.router, prefix=settings.api_prefix)
api_router.include_router(chat.router, prefix=settings.api_prefix)
api_router.include_router(ingestion.router, prefix=settings.api_prefix)
api_router.include_router(knowledge_base.router, prefix=settings.api_prefix)
