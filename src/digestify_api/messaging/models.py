from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Message(BaseModel):
    id: UUID
    destination: str
    type: str
    payload: str
    created_at: datetime
    scheduled_at: datetime


class Event(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Command(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    reply_to: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    scheduled_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Reply(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    reply_to: str
    command_id: UUID
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class HandledMessage(BaseModel):
    message_id: UUID
    handler_name: str
    handled_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
