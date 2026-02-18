from datetime import datetime, UTC
from uuid import UUID

from pydantic import BaseModel


class Message(BaseModel):
    id: UUID
    type: str
    payload: str
    created_at: datetime
    scheduled_at: datetime


class Event(Message):
    id: UUID
    type: str
    payload: str
    created_at: datetime = datetime.now(UTC)


class Command(Message):
    id: UUID
    type: str
    payload: str
    created_at: datetime
    scheduled_at: datetime


class HandledMessage(BaseModel):
    message_id: UUID
    handler_name: str
    handled_at: datetime
