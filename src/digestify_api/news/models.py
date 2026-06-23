from datetime import date, datetime
from datetime import time as time_
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
from pydantic_extra_types.timezone_name import TimeZoneName

from digestify_api.infrastructure.database import Document


class Schedule(BaseModel):
    time: time_ = Field(..., json_schema_extra={"example": "17:04:13"})
    timezone: TimeZoneName

    @field_validator("time")
    @classmethod
    def validate_schedule_time_is_naive(cls, time: time_) -> time_:
        if time.tzinfo is not None:
            raise ValueError(
                "Schedule time must not include a UTC offset. "
                "Provide local time and use schedule_timezone for timezone."
            )
        return time


class Language(StrEnum):
    EN_US = "en-US"
    TR_TR = "tr-TR"


class Checkpoint(Document):
    type: Literal["checkpoint"]
    last_seq: str


class Topic(Document):
    type: Literal["topic"]
    user_id: UUID
    name: str
    description: str
    language: Language
    schedule: Schedule


class User(Document):
    type: Literal["user"]
    is_deleted: bool
    topic_ids: list[UUID]
    window: date | None
    count: int


class Story(Document):
    type: Literal["story"]
    id: UUID
    title: str
    body: str
    language: Language
    created_at: datetime
