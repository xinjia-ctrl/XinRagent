from pydantic import BaseModel, ConfigDict


class CurrentUserResponse(BaseModel):
    id: int
    username: str
    nickname: str | None = None
    avatar: str | None = None
    email: str | None = None
    phone: str | None = None
    role: str

    model_config = ConfigDict(from_attributes=True)
