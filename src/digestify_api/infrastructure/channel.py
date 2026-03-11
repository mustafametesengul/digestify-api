from datetime import UTC, datetime
from uuid import UUID, uuid4

from asyncpg import Connection
from pydantic import BaseModel, Field

from digestify_api.infrastructure.message import Message, create_message
from digestify_api.infrastructure.outbox import create_outbox_message


class Channel:
    address: str | None


class Event(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Command(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    reply_to: Channel | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    scheduled_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Reply(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    command_id: UUID
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


async def enqueue_message(
    channel: Channel,
    connection: Connection,
    message: Event | Command | Reply,
) -> None:
    type = message.__class__.__name__
    payload = message.model_dump_json()
    id = message.id
    address = channel.address
    created_at = message.created_at

    if not address:
        raise ValueError("Channel address cannot be empty")

    if isinstance(message, Command):
        scheduled_at = message.scheduled_at
    else:
        scheduled_at = message.created_at

    converted_message = Message(
        id=id,
        channel=address,
        type=type,
        payload=payload,
        created_at=created_at,
        scheduled_at=scheduled_at,
    )
    await create_message(connection, converted_message)
    await create_outbox_message(connection, converted_message)
