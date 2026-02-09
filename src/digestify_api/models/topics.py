from datetime import date, datetime, time
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field
from pydantic_extra_types.timezone_name import TimeZoneName


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
    schedule_time: time
    schedule_timezone: TimeZoneName
    schedule_date: date


class Topic(TopicResponse):
    discarded: bool
    embedding: str
    schedule_version: int


class CreateTopicRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=50)
    description: str = Field(..., min_length=0, max_length=300)
    language: Language
    schedule_time: time
    schedule_timezone: TimeZoneName


class ChangeTopicScheduleRequest(BaseModel):
    topic_id: UUID
    schedule_time: time
    schedule_timezone: TimeZoneName
