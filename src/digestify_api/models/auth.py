from uuid import UUID

from pydantic import BaseModel


class Auth(BaseModel):
    id: UUID


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    refresh_token: str
