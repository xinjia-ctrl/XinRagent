from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.context import (
    REQUEST_ID_HEADER,
    create_request_context,
    reset_request_context,
    set_request_context,
)
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    register_exception_handlers(app)
    app.add_middleware(BaseHTTPMiddleware, dispatch=request_context_middleware)
    app.include_router(api_router)
    return app


async def request_context_middleware(request, call_next):
    context = create_request_context(request)
    token = set_request_context(context)
    try:
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = context.request_id
        return response
    finally:
        reset_request_context(token)


app = create_app()
