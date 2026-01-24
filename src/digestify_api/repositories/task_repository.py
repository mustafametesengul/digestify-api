from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from asyncpg import Connection
from fastapi import Depends

from digestify_api.db import get_connection
from digestify_api.models import TaskCreate, TaskRead, TaskStatus


class TaskRepository:
    def __init__(
        self,
        connection: Annotated[Connection, Depends(get_connection)],
    ) -> None:
        self._connection = connection

    async def create_task(self, task: TaskCreate) -> None:
        time = datetime.now(timezone.utc)
        await self._connection.execute(
            """
            INSERT INTO tasks
            (id, type, payload, scheduled_at, status, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            task.id,
            task.type,
            task.payload,
            task.scheduled_at,
            task.status,
            time,
            time,
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
        time = datetime.now(timezone.utc)
        await self._connection.execute(
            """
            UPDATE tasks
            SET status = $2, updated_at = $3
            WHERE id = $1
            """,
            task_id,
            status,
            time,
        )
