from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class Follow(BaseModel):
    user_id: UUID
    topic_id: UUID
    is_following: bool = True
    created_at: datetime
    updated_at: datetime | None


class Topic(BaseModel):
    id: UUID
    discarded: bool
    user_id: UUID
    name: str
    description: str
    language: str
    image_url: str | None
    is_active: bool
    followers_count: int
    created_at: datetime
    updated_at: datetime | None
