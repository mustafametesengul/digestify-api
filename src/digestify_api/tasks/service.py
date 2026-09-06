from collections.abc import AsyncGenerator, Callable, Collection
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from pydantic import JsonValue

from digestify_api.couchdb import Database, DocumentConflict, Repository
from digestify_api.tasks.task import (
    DailySchedule,
    LostLease,
    Schedule,
    Task,
    TaskStatus,
    bucket_for,
    timestamp,
    utc,
)


def _now() -> datetime:
    return datetime.now(UTC)


class TaskService:
    def __init__(
        self, database: Database, *, clock: Callable[[], datetime] = _now
    ) -> None:
        self._database = database
        self._tasks = Repository(Task, database)
        self._clock = clock

    async def init(self) -> None:
        await self._database.ensure_database()
        for deadline in ("available_at", "lease_until"):
            await self._database.ensure_index(
                name=f"task_{deadline}",
                fields=["type", "bucket", "status", deadline],
            )

    async def create(
        self,
        kind: str,
        payload: JsonValue = None,
        *,
        task_id: str | None = None,
        partition_key: str | None = None,
        scheduled_at: datetime | None = None,
        schedule: Schedule | None = None,
        max_attempts: int = 3,
        retry_delay: timedelta = timedelta(seconds=30),
    ) -> Task:
        """Create a task; reusing a caller-supplied ID raises DocumentConflict."""
        if task_id == "":
            raise ValueError("Task ID must not be empty.")
        now = utc(self._clock())
        first_run = utc(scheduled_at) if scheduled_at is not None else now
        if scheduled_at is None and isinstance(schedule, DailySchedule):
            first_run = schedule.next_after(now, now)
        identity = f"task:{task_id if task_id is not None else uuid4()}"
        key = partition_key if partition_key is not None else identity
        task = Task(
            id=identity,
            kind=kind,
            payload=payload,
            partition_key=key,
            bucket=bucket_for(key),
            schedule=schedule,
            scheduled_at=first_run,
            available_at=first_run,
            created_at=now,
            updated_at=now,
            max_attempts=max_attempts,
            retry_delay=retry_delay,
        )
        await self._tasks.save(task)
        return task

    async def get(self, task_id: str) -> Task | None:
        return await self._tasks.get(task_id)

    async def find(
        self,
        *,
        status: TaskStatus | None = None,
        partition_key: str | None = None,
        limit: int = 100,
    ) -> list[Task]:
        selector = {}
        if status is not None:
            selector["status"] = status
        if partition_key is not None:
            selector["partition_key"] = partition_key
        return await self._tasks.find(selector, limit=limit)

    async def cancel(self, task_id: str) -> Task | None:
        """Persist cancellation; running handlers observe it on renewal."""
        return await self._update(task_id, lambda task, now: task.cancel(now))

    async def candidates(
        self, buckets: Collection[int], kinds: Collection[str]
    ) -> list[Task]:
        now = timestamp(self._clock())
        tasks: list[Task] = []
        for status, deadline in (
            ("pending", "available_at"),
            ("running", "lease_until"),
        ):
            tasks.extend(
                await self._tasks.find(
                    {
                        "bucket": {"$in": list(buckets)},
                        "kind": {"$in": list(kinds)},
                        "status": status,
                        deadline: {"$lte": now},
                    }
                )
            )
        return sorted(tasks, key=lambda task: task.available_at)

    async def claim(
        self, task_id: str, worker_id: str, lease: timedelta
    ) -> Task | None:
        claimed = False

        def apply(task: Task, now: datetime) -> None:
            nonlocal claimed
            claimed = task.claim(worker_id, now, lease)

        task = await self._update(task_id, apply)
        return task if claimed else None

    async def renew(self, task_id: str, token: UUID, lease: timedelta) -> Task:
        task = await self._update(
            task_id, lambda task, now: task.renew(token, now, lease)
        )
        if task is None:
            raise LostLease(task_id)
        return task

    async def finish(
        self,
        task_id: str,
        token: UUID,
        *,
        result: JsonValue = None,
        error: str | None = None,
    ) -> Task:
        task = await self._update(
            task_id,
            lambda task, now: task.finish(token, now, result=result, error=error),
        )
        if task is None:
            raise LostLease(task_id)
        return task

    async def changes(self, since: str = "now") -> AsyncGenerator[str]:
        """Notification hints only; use get() for conflict-checked state."""
        async for change in self._database.changes(
            since=since, selector={"type": "task"}, include_docs=False
        ):
            yield change.seq

    async def _update(
        self, task_id: str, apply: Callable[[Task, datetime], None]
    ) -> Task | None:
        for attempt in range(3):
            task = await self._tasks.get(task_id)
            if task is None:
                return None
            before = task.model_dump()
            apply(task, utc(self._clock()))
            if task.model_dump() == before:
                return task
            try:
                await self._tasks.save(task)
                return task
            except DocumentConflict:
                if attempt == 2:
                    raise
        raise AssertionError("Unreachable")
