from datetime import datetime
from uuid import UUID

from asyncpg import Connection

from digestify_api.models import Task


async def create_task(conn: Connection, task: Task) -> None:
    await conn.execute(
        """
        INSERT INTO tasks
        (id, name, payload, scheduled_at, status, created_at, updated_at, error_message)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """,
        task.id,
        task.name,
        task.payload,
        task.scheduled_at,
        task.status,
        task.created_at,
        task.updated_at,
        task.error_message,
    )


async def read_task(conn: Connection, task_id: UUID, lock: bool = False) -> Task | None:
    query = "SELECT * FROM tasks WHERE id = $1"
    if lock:
        query += " FOR UPDATE"
    row = await conn.fetchrow(
        query,
        task_id,
    )
    if row is None:
        return None

    return Task.model_validate(dict(row))


async def update_task(conn: Connection, task: Task) -> None:
    await conn.execute(
        """
        UPDATE tasks
        SET name = $2,
            payload = $3,
            scheduled_at = $4,
            status = $5,
            created_at = $6,
            updated_at = $7,
            error_message = $8
        WHERE id = $1
        """,
        task.id,
        task.name,
        task.payload,
        task.scheduled_at,
        task.status,
        task.created_at,
        task.updated_at,
        task.error_message,
    )


async def get_pending_tasks(conn: Connection, until: datetime) -> list[Task]:
    rows = await conn.fetch(
        """
        SELECT *
        FROM tasks
        WHERE status = 'pending' AND scheduled_at <= $1
        ORDER BY scheduled_at ASC
        FOR UPDATE SKIP LOCKED
        """,
        until,
    )
    return [Task.model_validate(dict(row)) for row in rows]
