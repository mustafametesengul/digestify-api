from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class Language(StrEnum):
    EN_US = "en-US"
    TR_TR = "tr-TR"


class TopicResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    description: str
    language: Language
    image_url: str | None
    is_active: bool
    followers_count: int
    created_at: datetime
    updated_at: datetime | None


class Topic(TopicResponse):
    discarded: bool
    embedding: str


class CreateTopicRequest(BaseModel):
    id: UUID
    name: str = Field(..., min_length=3, max_length=50)
    description: str = Field(..., min_length=0, max_length=300)
    language: Language
