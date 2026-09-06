from datetime import datetime
from datetime import time as time_
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
from pydantic_extra_types.timezone_name import TimeZoneName

from digestify_api.couchdb import Document


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


class Fetch(BaseModel):
    topic_id: UUID
    story_ids: list[UUID]
    fetched_at: datetime


class Quota(Document):
    type: Literal["quota"]
    user_id: UUID
    fetch_history: list[Fetch]
    active_topics: list[UUID]
