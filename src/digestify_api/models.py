from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import DateTime, Field, SQLModel


class Entity(SQLModel):
    id: UUID = Field(primary_key=True, default_factory=uuid4)
    discarded: bool = Field(nullable=False, index=True, default=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
        sa_type=DateTime(timezone=True),  # type: ignore
        sa_column_kwargs={
            "onupdate": lambda: datetime.now(timezone.utc),
        },
    )
