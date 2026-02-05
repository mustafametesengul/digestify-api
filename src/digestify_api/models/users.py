from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel


class UserTier(StrEnum):
    FREE = "free"
    PREMIUM = "premium"
    ADMIN = "admin"


class UserResponse(BaseModel):
    id: UUID
    username: str | None
    tier: UserTier
    created_topics_count: int
    followed_topics_count: int
    active_topics_count: int
    created_at: datetime
    updated_at: datetime | None


class User(UserResponse):
    password_hash: str | None
    discarded: bool
