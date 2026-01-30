from datetime import datetime
from enum import StrEnum
from uuid import UUID

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
