from asyncpg import Connection

from digestify_api.infrastructure.models import Command, Event, Message, Reply
from digestify_api.infrastructure.queries import create_message, create_outbox_message


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
