from datetime import datetime, timezone
from uuid import UUID

from asyncpg import Connection
from pydantic import BaseModel

from digestify_api.tasks.models import TaskCreate, TaskRead, TaskStatus


class TaskRepository:
    def __init__(
        self,
        connection: Connection,
    ) -> None:
        self._connection = connection

    async def create_task(
        self,
        task_id: UUID,
        task_name: str,
        payload: BaseModel,
        scheduled_at: datetime | None = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        if scheduled_at is None or scheduled_at < now:
            scheduled_at = now
        task = TaskCreate(
            id=task_id,
            name=task_name,
            payload=payload.model_dump_json(),
            scheduled_at=scheduled_at,
            status=TaskStatus.PENDING,
        )
        await self._connection.execute(
            """
            INSERT INTO tasks
            (id, name, payload, scheduled_at, status, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            task.id,
            task.name,
            task.payload,
            task.scheduled_at,
            task.status,
            now,
            now,
        )

    async def read_task(self, task_id: UUID) -> TaskRead | None:
        row = await self._connection.fetchrow(
            "SELECT * FROM tasks WHERE id = $1",
            task_id,
        )

        if row is None:
            return None

        return TaskRead.model_validate(dict(row))

    async def update_task_status(self, task_id: UUID, status: TaskStatus) -> None:
        now = datetime.now(timezone.utc)
        await self._connection.execute(
            """
            UPDATE tasks
            SET status = $2, updated_at = $3
            WHERE id = $1
            """,
            task_id,
            status,
            now,
        )

    async def get_pending_tasks(self) -> list[TaskRead]:
        now = datetime.now(timezone.utc)
        rows = await self._connection.fetch(
            """
            SELECT *
            FROM tasks
            WHERE status = 'pending' AND scheduled_at <= $1
            ORDER BY scheduled_at ASC
            FOR UPDATE SKIP LOCKED
            """,
            now,
        )
        return [TaskRead.model_validate(dict(row)) for row in rows]
