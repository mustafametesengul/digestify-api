from datetime import date, time
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
from pydantic_extra_types.timezone_name import TimeZoneName


class Language(StrEnum):
    EN_US = "en-US"
    TR_TR = "tr-TR"


class TopicPublic(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    description: str
    language: Language
    image_url: str | None


class Schedule(BaseModel):
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


class CreateTopic(Schedule):
    name: str = Field(..., min_length=3, max_length=50)
    description: str = Field(..., min_length=0, max_length=300)
    language: Language


class ChangeTopicSchedule(Schedule):
    topic_id: UUID


class StoryPublic(BaseModel):
    id: UUID
    topic_id: UUID
    title: str
    image_url: str | None
    content: str
    language: Language


class FetchAndSaveStories(BaseModel):
    topic_id: UUID
    schedule_version: int
    schedule_time: time
    schedule_date: date
    schedule_timezone: TimeZoneName
