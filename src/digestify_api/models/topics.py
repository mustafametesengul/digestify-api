from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel


class Language(StrEnum):
    EN_US = "en-US"
    TR_TR = "tr-TR"


class Topic(BaseModel):
    id: UUID
    discarded: bool
    user_id: UUID
    name: str
    description: str
    language: Language
    image_url: str | None
    is_active: bool
    followers_count: int
    created_at: datetime
    updated_at: datetime | None
    embedding: list[float] | None
