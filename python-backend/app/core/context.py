from contextvars import ContextVar
from dataclasses import dataclass
from time import time
from uuid import uuid4

from fastapi import Request

from app.core.config import settings

REQUEST_ID_HEADER = "X-Request-Id"


@dataclass(frozen=True)
class RequestContext:
    request_id: str
    user_id: str | None = None
    expires_at: float | None = None

    @property
    def is_expired(self) -> bool:
        return self.expires_at is not None and time() >= self.expires_at


_request_context: ContextVar[RequestContext | None] = ContextVar(
    "request_context",
    default=None,
)


def create_request_context(request: Request) -> RequestContext:
    request_id = request.headers.get(REQUEST_ID_HEADER) or uuid4().hex
    ttl = max(settings.request_context_ttl_seconds, 0)
    return RequestContext(request_id=request_id, expires_at=time() + ttl if ttl else None)


def set_request_context(context: RequestContext) -> object:
    return _request_context.set(context)


def reset_request_context(token: object) -> None:
    _request_context.reset(token)


def get_request_context() -> RequestContext | None:
    context = _request_context.get()
    if context is None or context.is_expired:
        return None
    return context


def get_request_id(default: str = "-") -> str:
    context = get_request_context()
    if context is None:
        return default
    return context.request_id
