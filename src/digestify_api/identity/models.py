from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from digestify_api.infrastructure import Event


class UserResponse(BaseModel):
    id: UUID
    username: str | None
    created_at: datetime
    updated_at: datetime | None
    version: int


class User(UserResponse):
    password_hash: str | None
    discarded: bool


class SignUpWithUsernameRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=30)
    password: str = Field(..., min_length=8)


class SignInWithUsernameRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=30)
    password: str = Field(..., min_length=8)


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserSignedUp(Event):
    id: UUID
    username: str | None
    version: int


class UserDiscarded(Event):
    id: UUID
    version: int
