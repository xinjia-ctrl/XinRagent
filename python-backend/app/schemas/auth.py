from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token: str
    refresh_token: str
    refreshToken: str
    userId: str
    username: str
    role: str
    avatar: str | None = None
    token_type: str = "Bearer"
    expires_in: int
    refresh_expires_in: int


class RefreshTokenRequest(BaseModel):
    refresh_token: str
