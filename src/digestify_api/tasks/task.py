from datetime import UTC, datetime, time, timedelta
from hashlib import sha256
from typing import Annotated, Literal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from pydantic import (
    AwareDatetime,
    BaseModel,
    Field,
    JsonValue,
    field_serializer,
    field_validator,
)

from digestify_api.couchdb import Document

BUCKET_COUNT = 256
TaskStatus = Literal["pending", "running", "succeeded", "failed", "cancelled"]


def utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Task timestamps must include a timezone.")
    return value.astimezone(UTC)


def bucket_for(key: str) -> int:
    return int.from_bytes(sha256(key.encode("utf-8")).digest()[:8]) % BUCKET_COUNT


def timestamp(value: datetime) -> str:
    return utc(value).isoformat(timespec="microseconds").replace("+00:00", "Z")


class IntervalSchedule(BaseModel):
    kind: Literal["interval"] = "interval"
    every: timedelta = Field(gt=timedelta(0))

    def next_after(self, previous: datetime, now: datetime) -> datetime:
        previous, now = utc(previous), utc(now)
        steps = max(1, (now - previous) // self.every + 1)
        return previous + steps * self.every


class DailySchedule(BaseModel):
    kind: Literal["daily"] = "daily"
    time: time
    timezone: str

    @field_validator("time")
    @classmethod
    def naive_time(cls, value: time) -> time:
        if value.tzinfo is not None:
            raise ValueError("Use a local time without an offset and a timezone name.")
        return value.replace(fold=0)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (KeyError, ValueError) as error:
            raise ValueError("Unknown IANA timezone.") from error
        return value

    def next_after(self, previous: datetime, now: datetime) -> datetime:
        """Use the first fold; shift nonexistent times forward by the DST gap."""
        now = max(utc(previous), utc(now))
        zone = ZoneInfo(self.timezone)
        local_date = now.astimezone(zone).date()
        for day_offset in range(3):
            candidate = datetime.combine(
                local_date + timedelta(days=day_offset), self.time, tzinfo=zone
            ).astimezone(UTC)
            if candidate > now:
                return candidate
        raise ValueError("Cannot find the next daily occurrence.")


Schedule = Annotated[IntervalSchedule | DailySchedule, Field(discriminator="kind")]


class LostLease(Exception):
    """The claim expired, was cancelled, or belongs to another execution."""


class Task(Document):
    type: Literal["task"] = "task"
    kind: str = Field(min_length=1)
    payload: JsonValue = None
    partition_key: str
    bucket: int = Field(ge=0, lt=BUCKET_COUNT)
    schedule: Schedule | None = None
    status: TaskStatus = "pending"
    scheduled_at: AwareDatetime
    available_at: AwareDatetime
    created_at: AwareDatetime
    updated_at: AwareDatetime
    occurrence: int = Field(default=1, ge=1)
    attempts: int = Field(default=0, ge=0)
    max_attempts: int = Field(default=3, ge=1)
    retry_delay: timedelta = Field(default=timedelta(seconds=30), ge=timedelta(0))
    claim_token: UUID | None = None
    worker_id: str | None = None
    lease_until: AwareDatetime | None = None
    last_finished_at: AwareDatetime | None = None
    last_error: str | None = None
    last_result: JsonValue = None
    succeeded_runs: int = 0
    failed_runs: int = 0

    @field_validator(
        "scheduled_at",
        "available_at",
        "created_at",
        "updated_at",
        "lease_until",
        "last_finished_at",
    )
    @classmethod
    def utc_timestamp(cls, value: datetime | None) -> datetime | None:
        return utc(value) if value is not None else None

    @field_serializer(
        "scheduled_at",
        "available_at",
        "created_at",
        "updated_at",
        "lease_until",
        "last_finished_at",
        when_used="json",
    )
    def serialize_timestamp(self, value: datetime | None) -> str | None:
        return timestamp(value) if value is not None else None

    @property
    def idempotency_key(self) -> str:
        """Stable across retries and reclaims of this occurrence."""
        return f"{self.id}:{self.occurrence}"

    def claim(self, worker_id: str, now: datetime, lease: timedelta) -> bool:
        now = utc(now)
        if lease <= timedelta(0):
            raise ValueError("Lease must be positive.")
        if self.status == "pending":
            if self.available_at > now:
                return False
        elif self.status == "running":
            if self.lease_until is not None and self.lease_until > now:
                return False
        else:
            return False
        if self.attempts >= self.max_attempts:
            self._end_occurrence(now, error="Lease expired after the final attempt.")
            return False
        self.status = "running"
        self.attempts += 1
        self.claim_token = uuid4()
        self.worker_id = worker_id
        self.lease_until = now + lease
        self.updated_at = now
        return True

    def require_claim(self, token: UUID, now: datetime) -> None:
        if (
            self.status != "running"
            or self.claim_token != token
            or self.lease_until is None
            or self.lease_until <= utc(now)
        ):
            raise LostLease(self.id)

    def renew(self, token: UUID, now: datetime, lease: timedelta) -> None:
        now = utc(now)
        self.require_claim(token, now)
        if lease <= timedelta(0):
            raise ValueError("Lease must be positive.")
        self.lease_until = now + lease
        self.updated_at = now

    def finish(
        self,
        token: UUID,
        now: datetime,
        *,
        result: JsonValue = None,
        error: str | None = None,
    ) -> None:
        now = utc(now)
        self.require_claim(token, now)
        if error is not None and self.attempts < self.max_attempts:
            self.status = "pending"
            self.available_at = now + self.retry_delay
            self.last_error = error
            self.last_result = None
            self.last_finished_at = now
            self._clear_claim(now)
        else:
            self._end_occurrence(now, result=result, error=error)

    def cancel(self, now: datetime) -> None:
        if self.status not in ("succeeded", "failed", "cancelled"):
            self.status = "cancelled"
            self._clear_claim(utc(now))

    def _clear_claim(self, now: datetime) -> None:
        self.claim_token = None
        self.worker_id = None
        self.lease_until = None
        self.updated_at = now

    def _end_occurrence(
        self, now: datetime, *, result: JsonValue = None, error: str | None = None
    ) -> None:
        self.last_finished_at = now
        self.last_result = result
        self.last_error = error
        self.succeeded_runs += int(error is None)
        self.failed_runs += int(error is not None)
        self._clear_claim(now)
        if self.schedule is None:
            self.status = "succeeded" if error is None else "failed"
        else:
            self.status = "pending"
            self.scheduled_at = self.schedule.next_after(self.scheduled_at, now)
            self.available_at = self.scheduled_at
            self.occurrence += 1
            self.attempts = 0
