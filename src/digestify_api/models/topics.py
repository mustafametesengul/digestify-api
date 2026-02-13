from datetime import date, datetime, time
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
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
    schedule_time: time = Field(..., json_schema_extra={"example": "17:04:13"})
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
    schedule_time: time = Field(..., json_schema_extra={"example": "17:04:13"})
    schedule_timezone: TimeZoneName

    @field_validator("schedule_time")
    @classmethod
    def validate_schedule_time_is_naive(cls, schedule_time: time) -> time:
        if schedule_time.tzinfo is not None:
            raise ValueError(
                "schedule_time must not include a UTC offset. "
                "Provide local time and use schedule_timezone for timezone."
            )
        return schedule_time


class ChangeTopicScheduleRequest(BaseModel):
    topic_id: UUID
    schedule_time: time = Field(..., json_schema_extra={"example": "17:04:13"})
    schedule_timezone: TimeZoneName

    @field_validator("schedule_time")
    @classmethod
    def validate_schedule_time_is_naive(cls, schedule_time: time) -> time:
        if schedule_time.tzinfo is not None:
            raise ValueError(
                "schedule_time must not include a UTC offset. "
                "Provide local time and use schedule_timezone for timezone."
            )
        return schedule_time
