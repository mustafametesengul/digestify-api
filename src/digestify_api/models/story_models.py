from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class StoryCreate(BaseModel):
    id: UUID
    discarded: bool
    created_at: datetime
    updated_at: datetime
    topic_id: UUID
    title: str
    image_url: str | None
    content: str
    language: str


class StoryUpdate(StoryCreate):
    pass


class StoryRead(StoryUpdate):
    created_at: datetime
    updated_at: datetime
