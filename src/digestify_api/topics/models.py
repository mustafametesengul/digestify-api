from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class FollowCreate(BaseModel):
    user_id: UUID
    topic_id: UUID
    is_following: bool


class FollowUpdate(FollowCreate):
    pass


class FollowRead(FollowUpdate):
    created_at: datetime
    updated_at: datetime


class TopicCreate(BaseModel):
    id: UUID
    discarded: bool
    user_id: UUID
    name: str
    description: str
    language: str
    image_url: str | None
    is_active: bool
    followers_count: int


class TopicUpdate(TopicCreate):
    pass


class TopicRead(TopicUpdate):
    created_at: datetime
    updated_at: datetime
