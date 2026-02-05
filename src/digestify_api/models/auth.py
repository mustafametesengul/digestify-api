from uuid import UUID

from pydantic import BaseModel, Field


class Auth(BaseModel):
    id: UUID
    is_anonymous: bool


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class SignUpWithUsernameRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=30)
    password: str = Field(..., min_length=8)


class SignInWithUsernameRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=30)
    password: str = Field(..., min_length=8)
