from uuid import UUID

from pydantic import BaseModel


class Auth(BaseModel):
    id: UUID
    is_anonymous: bool


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str
