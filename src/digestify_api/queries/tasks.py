from datetime import datetime
from uuid import UUID

from asyncpg import Connection

from digestify_api.models import Task, TaskStatus


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


async def get_pending_tasks(
    conn: Connection,
    time: datetime,
    limit: int,
) -> list[Task]:
    rows = await conn.fetch(
        """
        SELECT *
        FROM tasks
        WHERE status = 'pending' AND scheduled_at <= $1
        ORDER BY scheduled_at ASC
        FOR UPDATE SKIP LOCKED
        LIMIT $2
        """,
        time,
        limit,
    )
    return [Task.model_validate(dict(row)) for row in rows]


async def mark_task_in_progress(
    conn: Connection,
    task_id: UUID,
    time: datetime,
) -> None:
    await conn.execute(
        """
        UPDATE tasks
        SET status = $3, updated_at = $4
        WHERE id = $1 AND status = $2
        """,
        task_id,
        TaskStatus.PENDING.value,
        TaskStatus.IN_PROGRESS.value,
        time,
    )


async def mark_task_completed(
    conn: Connection,
    task_id: UUID,
    time: datetime,
) -> None:
    await conn.execute(
        """
        UPDATE tasks
        SET status = $3, updated_at = $4
        WHERE id = $1 AND status = $2
        """,
        task_id,
        TaskStatus.IN_PROGRESS.value,
        TaskStatus.COMPLETED.value,
        time,
    )


async def mark_task_failed(
    conn: Connection,
    task_id: UUID,
    error_message: str,
    time: datetime,
) -> None:
    await conn.execute(
        """
        UPDATE tasks
        SET status = $3, error_message = $4, updated_at = $5
        WHERE id = $1 AND status = $2
        """,
        task_id,
        TaskStatus.IN_PROGRESS.value,
        TaskStatus.FAILED.value,
        error_message,
        time,
    )
