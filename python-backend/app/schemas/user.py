from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CurrentUserResponse(BaseModel):
    id: str
    userId: str
    username: str
    nickname: str | None = None
    avatar: str | None = None
    email: str | None = None
    phone: str | None = None
    role: str

    model_config = ConfigDict(from_attributes=True)


class UserItem(BaseModel):
    id: str
    username: str
    role: str
    avatar: str | None = None
    createTime: datetime | None = None
    updateTime: datetime | None = None


class UserPageResponse(BaseModel):
    records: list[UserItem]
    total: int
    size: int
    current: int
    pages: int


class UserCreateRequest(BaseModel):
    username: str
    password: str
    role: str = "user"
    avatar: str | None = None


class UserUpdateRequest(BaseModel):
    username: str | None = None
    password: str | None = None
    role: str | None = None
    avatar: str | None = None


class ChangePasswordRequest(BaseModel):
    currentPassword: str
    newPassword: str
