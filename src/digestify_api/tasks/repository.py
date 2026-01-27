from datetime import datetime, timezone
from uuid import UUID

from asyncpg import Connection

from digestify_api.tasks.models import Task, TaskStatus


class TaskRepository:
    def __init__(
        self,
        connection: Connection,
    ) -> None:
        self._connection = connection

    async def create_task(self, task: Task) -> None:
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
            task.created_at,
            task.updated_at,
        )

    async def read_task(self, task_id: UUID) -> Task | None:
        row = await self._connection.fetchrow(
            "SELECT * FROM tasks WHERE id = $1",
            task_id,
        )

        if row is None:
            return None

        return Task.model_validate(dict(row))

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

    async def get_pending_tasks(self) -> list[Task]:
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
        return [Task.model_validate(dict(row)) for row in rows]
