from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from digestify_api.infrastructure import Event


class UserPublic(BaseModel):
    id: UUID
    username: str | None


class SignUpWithUsername(BaseModel):
    username: str = Field(..., min_length=4, max_length=32)
    password: str = Field(..., min_length=8)


class SignInWithUsername(BaseModel):
    username: str = Field(..., min_length=4, max_length=32)
    password: str = Field(..., min_length=8)


class RefreshToken(BaseModel):
    refresh_token: str


class UserSignedUp(Event):
    user_id: UUID
    username: str | None
    version: int


class UserDeleted(Event):
    user_id: UUID
    version: int


class UserClaims(BaseModel):
    id: UUID
    is_anonymous: bool


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["Bearer"] = "Bearer"
