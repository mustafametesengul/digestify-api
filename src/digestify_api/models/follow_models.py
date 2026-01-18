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
