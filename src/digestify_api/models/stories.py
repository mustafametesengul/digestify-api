from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from digestify_api.models import topics


class StoryResponse(BaseModel):
    id: UUID
    topic_id: UUID
    title: str
    image_url: str | None
    content: str
    language: topics.Language
    created_at: datetime
    updated_at: datetime | None


class Story(StoryResponse):
    discarded: bool
    embedding: str


class FetchAndSaveStoriesTask(BaseModel):
    topic_id: UUID
    schedule_version: int
