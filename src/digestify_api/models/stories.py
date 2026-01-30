from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class Story(BaseModel):
    id: UUID
    discarded: bool
    topic_id: UUID
    title: str
    image_url: str | None
    content: str
    language: str
    created_at: datetime
    updated_at: datetime | None
