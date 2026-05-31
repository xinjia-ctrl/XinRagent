from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token: str
    userId: str
    username: str
    role: str
    avatar: str | None = None
    token_type: str = "Bearer"
    expires_in: int
