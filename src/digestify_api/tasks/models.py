from datetime import datetime
from enum import StrEnum
from types import FunctionType
from typing import Awaitable, Callable, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel


class TaskStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class Task(BaseModel):
    id: UUID
    name: str
    payload: dict
    scheduled_at: datetime
    status: TaskStatus
    created_at: datetime
    updated_at: datetime | None
    error_message: str | None


T = TypeVar("T", bound=BaseModel)
AsyncTaskHandler = Callable[[T], Awaitable[None]]


def from_handler(
    self,
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
        payload=payload.model_dump(mode="json"),
        scheduled_at=scheduled_at,
        status=TaskStatus.PENDING,
        created_at=created_at,
        updated_at=None,
        error_message=None,
    )
    return task
