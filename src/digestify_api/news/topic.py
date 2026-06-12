from datetime import UTC, date, datetime
from datetime import time as time_
from enum import StrEnum
from typing import Annotated, Literal, override
from uuid import UUID

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


class State(BaseModel):
    type: Literal["TopicState"] = "TopicState"
    user_id: UUID
    name: str
    description: str
    language: Language
    is_active: bool
    schedule: Schedule
    schedule_version: int
    last_execution_date: date | None


class TopicCreated(BaseModel):
    type: Literal["TopicCreated"] = "TopicCreated"
    user_id: UUID
    name: str
    description: str
    language: Language
    schedule: Schedule
    created_at: datetime


class TopicActivated(BaseModel):
    type: Literal["TopicActivated"] = "TopicActivated"
    user_id: UUID
    created_at: datetime


type Event = Annotated[TopicCreated | TopicActivated, Field(discriminator="type")]


class Topic(Aggregate[State, Event]):
    @override
    def apply(self, event: Event) -> None:
        match event:
            case TopicCreated():
                self._state = State(
                    user_id=event.user_id,
                    name=event.name,
                    description=event.description,
                    language=event.language,
                    is_active=False,
                    schedule=event.schedule,
                    schedule_version=0,
                    last_execution_date=None,
                )
            case TopicActivated():
                if self._state is not None:
                    self._state.is_active = True

    def create(
        self,
        user_id: UUID,
        name: str,
        description: str,
        language: Language,
        schedule: Schedule,
    ) -> None:
        self._emit(
            TopicCreated(
                user_id=user_id,
                name=name,
                description=description,
                language=language,
                schedule=schedule,
                created_at=datetime.now(UTC),
            )
        )

    def activate(self) -> None:
        if self._state is None:
            raise ValueError("Topic does not exist")
        if self._state.is_active:
            raise ValueError("Topic is already active")
        self._emit(
            TopicActivated(
                user_id=self._state.user_id,
                created_at=datetime.now(UTC),
            )
        )

    def update_schedule(self, schedule: Schedule) -> None:
        if self._state is None:
            raise ValueError("Topic does not exist")
        self._state.schedule = schedule
        self._state.schedule_version += 1
