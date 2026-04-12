from datetime import UTC, date, datetime
from datetime import time as time_
from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID, uuid7

from pydantic import BaseModel, Field, field_validator
from pydantic_extra_types.timezone_name import TimeZoneName

from digestify_api.infrastructure.entity import Entity, Message


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


class CreateTopic(Message):
    type: Literal["CreateTopic"] = "CreateTopic"
    topic_id: UUID = Field(default_factory=uuid7)
    user_id: UUID
    name: str
    description: str
    language: Language
    schedule: Schedule
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ActivateTopic(Message):
    type: Literal["ActivateTopic"] = "ActivateTopic"
    topic_id: UUID
    user_id: UUID
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Topic(Entity):
    type: Literal["Topic"] = "Topic"
    user_id: UUID
    name: str
    description: str
    language: Language
    is_active: bool
    schedule: Schedule
    schedule_version: int
    last_execution_date: date | None

    @classmethod
    def create(
        cls,
        command: CreateTopic,
    ) -> Self:
        topic = cls(
            user_id=command.user_id,
            name=command.name,
            description=command.description,
            language=command.language,
            is_active=True,
            schedule=command.schedule,
            schedule_version=1,
            last_execution_date=None,
        )
        return topic

    def activate(self) -> None:
        pass

    def deactivate(self) -> None:
        pass
