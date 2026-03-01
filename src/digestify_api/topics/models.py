from datetime import date, datetime, time
from uuid import UUID

from pydantic import BaseModel
from pydantic_extra_types.timezone_name import TimeZoneName

from digestify_api.topics import schemas


class User(BaseModel):
    id: UUID
    created_topics_count: int
    identity_version: int
    membership_version: int
    tier: str
    is_deleted: bool
    created_at: datetime
    updated_at: datetime | None


class Topic(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    description: str
    language: schemas.Language
    image_url: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime | None
    schedule_time: time
    schedule_timezone: TimeZoneName
    schedule_version: int
    last_execution_date: date
    is_deleted: bool


class Story(BaseModel):
    id: UUID
    topic_id: UUID
    title: str
    image_url: str | None
    content: str
    language: schemas.Language
    created_at: datetime
    updated_at: datetime | None
    is_deleted: bool
