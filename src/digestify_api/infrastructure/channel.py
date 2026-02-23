from datetime import UTC, datetime
from uuid import UUID, uuid4

from asyncpg import Connection
from pydantic import BaseModel, Field

from digestify_api.infrastructure.message import Message, create_message
from digestify_api.infrastructure.outbox import create_outbox_message


class Event(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    producer: str | None = None
    version: int | None = None


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


class Channel:
    def __init__(self, name: str | None = None):
        self._name = name

    def set_name(self, name: str) -> None:
        self._name = name

    def get_name(self) -> str:
        if not self._name:
            raise ValueError("Channel name is not set.")
        return self._name

    async def _save_message(self, connection: Connection, message: Message) -> None:
        await create_message(connection, message)
        await create_outbox_message(connection, message)

    async def save_event(self, connection: Connection, event: Event) -> None:
        name = self.get_name()
        message = Message(
            id=event.id,
            channel=f"{name}:events",
            type=event.__class__.__name__,
            payload=event.model_dump_json(),
            created_at=event.created_at,
            scheduled_at=event.created_at,
            producer=event.producer,
            version=event.version,
        )
        await self._save_message(connection, message)

    async def save_command(self, connection: Connection, command: Command) -> None:
        name = self.get_name()
        message = Message(
            id=command.id,
            channel=f"{name}:commands",
            type=command.__class__.__name__,
            payload=command.model_dump_json(),
            created_at=command.created_at,
            scheduled_at=command.scheduled_at,
        )
        await self._save_message(connection, message)

    async def save_reply(self, connection: Connection, reply: Reply) -> None:
        message = Message(
            id=reply.id,
            channel=f"{reply.reply_to}:replies",
            type=reply.__class__.__name__,
            payload=reply.model_dump_json(),
            created_at=reply.created_at,
            scheduled_at=reply.created_at,
        )
        await self._save_message(connection, message)
