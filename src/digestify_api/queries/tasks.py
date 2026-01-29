from datetime import datetime
from enum import StrEnum
from types import FunctionType
from typing import Awaitable, Callable, TypeVar
from uuid import UUID, uuid4

from asyncpg import Connection
from pydantic import BaseModel


class TaskStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class Task(BaseModel):
    id: UUID
    name: str
    payload: str
    scheduled_at: datetime
    status: TaskStatus
    created_at: datetime
    updated_at: datetime | None
    error_message: str | None


T = TypeVar("T", bound=BaseModel)
AsyncTaskHandler = Callable[[T], Awaitable[None]]


def from_handler(
    handler: AsyncTaskHandler[T],
    payload: T,
    created_at: datetime,
    task_id: UUID | None = None,
    scheduled_at: datetime | None = None,
) -> Task:
    if not isinstance(handler, FunctionType):
        raise ValueError("Handler must be a function")

    if scheduled_at is None:
        scheduled_at = created_at

    if task_id is None:
        task_id = uuid4()

    task = Task(
        id=task_id,
        name=handler.__name__,
        payload=payload.model_dump_json(),
        scheduled_at=scheduled_at,
        status=TaskStatus.PENDING,
        created_at=created_at,
        updated_at=None,
        error_message=None,
    )
    return task


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
