from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel


class TaskStatus(StrEnum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class TaskCreate(BaseModel):
    id: UUID
    name: str
    payload: str
    scheduled_at: datetime
    status: TaskStatus


class TaskUpdate(TaskCreate):
    pass


class TaskRead(TaskUpdate):
    created_at: datetime
    updated_at: datetime
