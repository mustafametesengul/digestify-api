from datetime import datetime
from enum import StrEnum
from types import FunctionType
from typing import Awaitable, Callable, TypeVar
from uuid import UUID

from pydantic import BaseModel


class TaskStatus(StrEnum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Task(BaseModel):
    id: UUID
    name: str
    payload: dict
    scheduled_at: datetime
    status: TaskStatus
    created_at: datetime
    updated_at: datetime | None


T = TypeVar("T", bound=BaseModel)
AsyncTaskHandler = Callable[[T], Awaitable[None]]


def handler_to_task(
    self,
    task_id: UUID,
    handler: AsyncTaskHandler[T],
    payload: T,
    scheduled_at: datetime,
    created_at: datetime,
) -> Task:
    if not isinstance(handler, FunctionType):
        raise ValueError("Handler must be a function")

    task = Task(
        id=task_id,
        name=handler.__name__,
        payload=payload.model_dump(mode="json"),
        scheduled_at=scheduled_at,
        status=TaskStatus.PENDING,
        created_at=created_at,
        updated_at=None,
    )
    return task
