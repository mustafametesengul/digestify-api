from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from digestify_api.models.topics import Language


class StoryPublic(BaseModel):
    id: UUID
    topic_id: UUID
    title: str
    image_url: str | None
    content: str
    language: Language
    created_at: datetime
    updated_at: datetime | None


class Story(StoryPublic):
    discarded: bool
    embedding: str
