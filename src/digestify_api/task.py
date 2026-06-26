import asyncio
from datetime import datetime, timedelta, UTC
from datetime import time as time_
from zoneinfo import ZoneInfo
from uuid import UUID
from typing import Awaitable, Callable, Literal
from digestify_api.couchdb import Document, Database, DocumentConflict
from pydantic import BaseModel, Field, field_validator
from pydantic_extra_types.timezone_name import TimeZoneName


# How long a claim is trusted before another worker may reclaim the task. If a
# worker crashes mid-run, the task is stuck `running` until this elapses, after
# which any worker is free to pick it up again.
DEFAULT_LEASE = timedelta(minutes=10)

Handler = Callable[["RecurringTask"], Awaitable[None]]


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
    type: Literal["recurring_task"] = "recurring_task"
    user_id: UUID
    schedule: Schedule
    # Always stored in UTC so range comparisons across workers are unambiguous.
    scheduled_at: datetime
    is_active: bool
    # None means "not claimed". A datetime marks when a worker took the task;
    # it doubles as the lease start, so a crashed worker's claim expires.
    running_since: datetime | None = None

    def _next_run(self, now: datetime) -> datetime:
        """The next wall-clock occurrence of the schedule, returned in UTC.

        We resolve "today" in the schedule's own timezone (not UTC) so a
        23:00 local time near a UTC day boundary lands on the right day, and
        recombine rather than add a timedelta so DST shifts stay correct.
        """
        tz = ZoneInfo(self.schedule.timezone)
        local_now = now.astimezone(tz)
        run = datetime.combine(local_now.date(), self.schedule.time, tzinfo=tz)
        if run <= local_now:
            run = datetime.combine(
                local_now.date() + timedelta(days=1), self.schedule.time, tzinfo=tz
            )
        return run.astimezone(UTC).replace(microsecond=0)

    def change_schedule(self, new_schedule: Schedule, now: datetime) -> None:
        self.schedule = new_schedule
        self.scheduled_at = self._next_run(now)

    def activate(self, now: datetime) -> None:
        self.is_active = True
        self.scheduled_at = self._next_run(now)

    def deactivate(self) -> None:
        self.is_active = False

    def is_leased(self, now: datetime, lease: timedelta) -> bool:
        return self.running_since is not None and now - self.running_since < lease

    def claim(self, now: datetime, lease: timedelta) -> None:
        if not self.is_active:
            raise ValueError("Cannot claim an inactive task.")
        if self.is_leased(now, lease):
            raise ValueError("Task is already claimed by a live worker.")
        self.running_since = now.replace(microsecond=0)

    def complete(self, now: datetime) -> None:
        self.running_since = None
        self.scheduled_at = self._next_run(now)


class TaskService:
    def __init__(self, database: Database, lease: timedelta = DEFAULT_LEASE) -> None:
        self._database = database
        self._lease = lease
        # Set by the changes-feed watcher to interrupt the scheduler's sleep.
        self._wakeup = asyncio.Event()
        self._running: set[asyncio.Task[None]] = set()

    async def init(self) -> None:
        await self._database.ensure_database()
        await self._database.ensure_index(
            fields=["is_active", "scheduled_at"],
            name="recurring_task_active_scheduled_index",
        )

    async def create(
        self,
        task_id: UUID,
        user_id: UUID,
        schedule: Schedule,
        now: datetime,
    ) -> None:
        task = RecurringTask(
            type="recurring_task",
            id=str(task_id),
            user_id=user_id,
            schedule=schedule,
            scheduled_at=now,
            is_active=True,
            running_since=None,
        )
        task.scheduled_at = task._next_run(now)
        await self._database.save(task)

    async def run(self, handler: Handler) -> None:
        """Run this worker until cancelled.

        Spawn one of these per process; they coordinate purely through CouchDB.
        Cancel the task (or the surrounding TaskGroup) to stop.
        """
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self._watch_changes())
            tg.create_task(self._schedule_loop(handler))

    async def _watch_changes(self) -> None:
        # `since="now"` skips replaying history — the scheduler loop reads
        # current state directly; the feed only needs to signal *future* edits.
        # We don't care which task changed, only that we should recompute.
        async for _change in self._database.changes(
            RecurringTask,
            since="now",
            selector={"type": "recurring_task"},
            include_docs=False,
        ):
            self._wakeup.set()

    async def _schedule_loop(self, handler: Handler) -> None:
        while True:
            self._wakeup.clear()
            sleep_for = await self._tick(handler)
            try:
                # Wake at the next deadline, or earlier if a change arrives.
                # sleep_for is None when nothing is scheduled: wait indefinitely
                # for a change rather than busy-looping.
                await asyncio.wait_for(self._wakeup.wait(), timeout=sleep_for)
            except TimeoutError:
                pass

    async def _tick(self, handler: Handler) -> float | None:
        """Claim and run every due task; return seconds until the next wake."""
        now = datetime.now(UTC)
        active = await self._database.find(
            RecurringTask,
            selector={"is_active": True},
        )

        next_wake: datetime | None = None
        for task in active:
            if task.scheduled_at <= now:
                if task.running_since is not None and task.is_leased(now, self._lease):
                    # Owned by another worker; revisit when its lease expires.
                    next_wake = _earliest(next_wake, task.running_since + self._lease)
                    continue
                try:
                    task.claim(now, self._lease)
                    await self._database.save(task)
                except DocumentConflict, ValueError:
                    continue  # another worker won the claim
                self._spawn(self._run(task, handler))
            else:
                next_wake = _earliest(next_wake, task.scheduled_at)

        if next_wake is None:
            return None
        return max((next_wake - datetime.now(UTC)).total_seconds(), 0.0)

    async def _run(self, task: RecurringTask, handler: Handler) -> None:
        try:
            await handler(task)
        finally:
            await self._complete(task)

    async def _complete(self, task: RecurringTask) -> None:
        # The doc may have changed under us (e.g. user edited the schedule);
        # reload and reapply rather than clobbering or leaking the lease.
        for _ in range(3):
            task.complete(datetime.now(UTC))
            try:
                await self._database.save(task)
                return
            except DocumentConflict:
                fresh = await self._database.get(RecurringTask, task.id)
                if fresh is None or fresh.running_since is None:
                    return  # deleted, or already completed by a reclaiming worker
                task = fresh

    def _spawn(self, coro: Awaitable[None]) -> None:
        # Run handlers off the claim loop so one slow task doesn't block
        # claiming the rest; keep a reference so they aren't GC'd mid-flight.
        task = asyncio.ensure_future(coro)
        self._running.add(task)
        task.add_done_callback(self._running.discard)


def _earliest(current: datetime | None, candidate: datetime) -> datetime:
    return candidate if current is None else min(current, candidate)
