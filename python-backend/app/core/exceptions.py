import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.responses import fail, json_response

logger = logging.getLogger(__name__)


class RagentException(Exception):
    def __init__(
        self,
        message: str,
        code: str = "500",
        status_code: int = status.HTTP_400_BAD_REQUEST,
        data: Any | None = None,
    ) -> None:
        self.message = message
        self.code = code
        self.status_code = status_code
        self.data = data
        super().__init__(message)


def bad_request(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)


async def ragent_exception_handler(_: Request, exc: RagentException) -> JSONResponse:
    return json_response(fail(code=exc.code, message=exc.message, data=exc.data), exc.status_code)


async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    message = str(exc.detail) if exc.detail else "request failed"
    return json_response(fail(code=str(exc.status_code), message=message), exc.status_code)


async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return json_response(
        fail(code="422", message="request validation failed", data=exc.errors()),
        status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception", exc_info=exc)
    return json_response(
        fail(code="500", message="internal server error"),
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RagentException, ragent_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
