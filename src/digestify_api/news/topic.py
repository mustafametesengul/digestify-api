from datetime import date, datetime
from datetime import time as time_
from enum import StrEnum
from typing import Literal, Self
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, field_validator
from pydantic_extra_types.timezone_name import TimeZoneName

from digestify_api.infrastructure.couchdb import Document

# A user may have at most this many topics active at once. Each active topic
# costs one scheduled (LLM-backed) fetch per day, so this also bounds a user's
# daily scheduled spend — see `digestify_api.news.quota`.
MAX_ACTIVE_TOPICS = 5


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


class Topic(Document):
    type: Literal["topic"] = "topic"
    user_id: UUID
    name: str
    description: str
    language: Language
    is_active: bool = False
    schedule: Schedule
    # The local date this topic last produced stories. The scheduler uses it to
    # run a topic at most once per local day; `None` means it has never run.
    last_execution_date: date | None = None

    @classmethod
    def create(
        cls,
        *,
        user_id: UUID,
        name: str,
        description: str,
        language: Language,
        schedule: Schedule,
    ) -> Self:
        # Topics start inactive; activation is a deliberate, capped action so it
        # cannot be used to silently exceed the active-topic limit.
        return cls(
            id=str(uuid4()),
            user_id=user_id,
            name=name,
            description=description,
            language=language,
            schedule=schedule,
        )

    def update_schedule(self, schedule: Schedule) -> None:
        self.schedule = schedule

    def activate(self) -> None:
        self.is_active = True

    def deactivate(self) -> None:
        self.is_active = False

    def local_date(self, now: datetime) -> date:
        """The calendar date `now` falls on in this topic's own timezone."""
        return now.astimezone(ZoneInfo(self.schedule.timezone)).date()

    def is_due(self, now: datetime) -> bool:
        """Whether the scheduler should fetch stories for this topic at `now`.

        A topic is due once per local day, at or after its scheduled local
        time, and only while active.
        """
        if not self.is_active:
            return False

        zone = ZoneInfo(self.schedule.timezone)
        local_now = now.astimezone(zone)

        if (
            self.last_execution_date is not None
            and self.last_execution_date >= local_now.date()
        ):
            return False

        scheduled = datetime.combine(local_now.date(), self.schedule.time, tzinfo=zone)
        return local_now >= scheduled

    def mark_executed(self, now: datetime) -> None:
        self.last_execution_date = self.local_date(now)
