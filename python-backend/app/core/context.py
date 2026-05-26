from contextvars import ContextVar
from dataclasses import dataclass
from uuid import uuid4

from fastapi import Request

REQUEST_ID_HEADER = "X-Request-Id"


@dataclass(frozen=True)
class RequestContext:
    request_id: str
    user_id: str | None = None


_request_context: ContextVar[RequestContext | None] = ContextVar(
    "request_context",
    default=None,
)


def create_request_context(request: Request) -> RequestContext:
    request_id = request.headers.get(REQUEST_ID_HEADER) or uuid4().hex
    return RequestContext(request_id=request_id)


def set_request_context(context: RequestContext) -> object:
    return _request_context.set(context)


def reset_request_context(token: object) -> None:
    _request_context.reset(token)


def get_request_context() -> RequestContext | None:
    return _request_context.get()


def get_request_id(default: str = "-") -> str:
    context = get_request_context()
    if context is None:
        return default
    return context.request_id
