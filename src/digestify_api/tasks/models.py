from sqlmodel import Field

from digestify_api.models import Entity

from datetime import datetime, timezone
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from digestify_api.db import AsyncSession, get_session
from digestify_api.tasks.schemas import TaskStatus

SCHEMA = "tasks"


class Task(Entity, table=True):
    __table_args__ = {"schema": SCHEMA}
    __tablename__ = "tasks"
    status: TaskStatus = Field(
        nullable=False,
        index=True,
        default=TaskStatus.PENDING,
    )
    type: str = Field(nullable=False)
    payload: dict = Field(sa_type=JSONB, nullable=False)
    scheduled_at: datetime = Field(
        nullable=False,
        sa_type=TIMESTAMP(timezone=True),  # type: ignore
        index=True,
        default_factory=lambda: datetime.now(timezone.utc),
    )
