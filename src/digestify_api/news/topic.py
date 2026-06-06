from datetime import UTC, date, datetime
from datetime import time as time_
from enum import StrEnum
from typing import Annotated, Literal, override
from uuid import UUID, uuid7

from pydantic import BaseModel, Field, field_validator
from pydantic_extra_types.timezone_name import TimeZoneName

from rillo import Aggregate


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


class CreateTopic(BaseModel):
    type: Literal["CreateTopic"] = "CreateTopic"
    topic_id: UUID = Field(default_factory=uuid7)
    user_id: UUID
    name: str
    description: str
    language: Language
    schedule: Schedule
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ActivateTopic(BaseModel):
    type: Literal["ActivateTopic"] = "ActivateTopic"
    topic_id: UUID
    user_id: UUID
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TopicCreated(BaseModel):
    type: Literal["TopicCreated"] = "TopicCreated"
    topic_id: UUID
    user_id: UUID
    name: str
    description: str
    language: Language
    schedule: Schedule
    created_at: datetime


class TopicActivated(BaseModel):
    type: Literal["TopicActivated"] = "TopicActivated"
    topic_id: UUID
    user_id: UUID
    created_at: datetime


class TopicState(BaseModel):
    type: Literal["Topic"] = "Topic"
    user_id: UUID
    name: str
    description: str
    language: Language
    is_active: bool
    schedule: Schedule
    schedule_version: int
    last_execution_date: date | None


type TopicEvent = Annotated[TopicCreated | TopicActivated, Field(discriminator="type")]
type TopicCommand = Annotated[CreateTopic, Field(discriminator="type")]


class Topic(Aggregate[TopicState, TopicEvent, TopicCommand]):
    @override
    def apply(self, event: TopicEvent) -> None:
        match event:
            case CreateTopic():
                self.state = TopicState.model_validate(
                    event.model_dump(exclude={"type"})
                )
            case ActivateTopic():
                self.state.is_active = True

    @override
    def execute(self, command: TopicCommand) -> None:
        match command:
            case CreateTopic():
                self._emit(
                    TopicCreated.model_validate(command.model_dump(exclude={"type"}))
                )
