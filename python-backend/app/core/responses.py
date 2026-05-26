from typing import Generic, TypeVar

from fastapi.responses import JSONResponse
from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: str = "0"
    message: str = "success"
    data: T | None = None


def success(data: T | None = None, message: str = "success") -> ApiResponse[T]:
    return ApiResponse(message=message, data=data)


def fail(code: str, message: str, data: T | None = None) -> ApiResponse[T]:
    return ApiResponse(code=code, message=message, data=data)


def json_response(response: ApiResponse[T], status_code: int = 200) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=response.model_dump())
