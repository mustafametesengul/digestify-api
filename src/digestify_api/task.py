from datetime import datetime, timedelta
from datetime import time as time_
from uuid import UUID, uuid4
from typing import Literal
from digestify_api.couchdb import Document, Database
from pydantic import BaseModel, Field, field_validator
from pydantic_extra_types.timezone_name import TimeZoneName


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


class RecurringTask(Document):
    type: Literal["recurring_task"]
    user_id: UUID
    schedule: Schedule
    scheduled_at: datetime
    is_active: bool
    is_running: bool

    @staticmethod
    def _calculate_next_scheduled_at(now: datetime, schedule: Schedule) -> datetime:
        # Calculate the next scheduled time based on the current schedule
        next_scheduled_time = datetime.combine(
            now.date(), schedule.time, tzinfo=schedule.timezone
        )
        if next_scheduled_time <= now:
            next_scheduled_time = datetime.combine(
                now.date() + timedelta(days=1),
                schedule.time,
                tzinfo=schedule.timezone,
            )
        return next_scheduled_time

    def change_schedule(self, new_schedule: Schedule, now: datetime) -> None:
        self.schedule = new_schedule
        self.scheduled_at = self._calculate_next_scheduled_at(now, new_schedule)

    def activate(self, now: datetime) -> None:
        self.is_active = True
        self.scheduled_at = self._calculate_next_scheduled_at(now, self.schedule)

    def mark_as_running(self) -> None:
        if self.is_running:
            raise ValueError("Task is already marked as running.")
        if not self.is_active:
            raise ValueError("Cannot mark a task as running if it is not active.")
        self.is_running = True

    def mark_as_completed(self, now: datetime) -> None:
        if not self.is_running:
            raise ValueError("Cannot mark a task as completed if it is not running.")
        self.is_running = False
        self.scheduled_at = self._calculate_next_scheduled_at(now, self.schedule)


class TaskService:
    def __init__(self, database: Database) -> None:
        self._database = database
