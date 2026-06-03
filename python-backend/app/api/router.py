from fastapi import APIRouter

from app.api.v1 import (
    auth,
    chat,
    conversations,
    documents,
    health,
    ingestion,
    ingestion_admin,
    intent_tree,
    knowledge_base,
    query_term_mappings,
    sample_questions,
    traces,
    users,
)
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router, prefix=settings.api_prefix)
api_router.include_router(users.router, prefix=settings.api_prefix)
api_router.include_router(conversations.router, prefix=settings.api_prefix)
api_router.include_router(chat.router, prefix=settings.api_prefix)
api_router.include_router(ingestion.router, prefix=settings.api_prefix)
api_router.include_router(ingestion_admin.router, prefix=settings.api_prefix)
api_router.include_router(intent_tree.router, prefix=settings.api_prefix)
api_router.include_router(knowledge_base.router, prefix=settings.api_prefix)
api_router.include_router(documents.router, prefix=settings.api_prefix)
api_router.include_router(query_term_mappings.router, prefix=settings.api_prefix)
api_router.include_router(sample_questions.router, prefix=settings.api_prefix)
api_router.include_router(traces.router, prefix=settings.api_prefix)
