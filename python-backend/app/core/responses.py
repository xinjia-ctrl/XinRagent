from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: str = "0"
    message: str = "success"
    data: T | None = None


def success(data: T | None = None) -> ApiResponse[T]:
    return ApiResponse(data=data)
