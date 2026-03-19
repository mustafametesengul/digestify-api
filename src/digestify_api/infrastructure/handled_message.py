from datetime import UTC, datetime
from uuid import UUID

from asyncpg import Connection
from pydantic import BaseModel, Field


class HandledMessage(BaseModel):
    message_id: UUID
    handler_name: str
    handled_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


async def create_handled_message(
    conn: Connection, handled_message: HandledMessage
) -> None:
    await conn.execute(
        """
        INSERT INTO handled_messages
        (message_id, handler_name, handled_at)
        VALUES ($1, $2, $3)
        """,
        handled_message.message_id,
        handled_message.handler_name,
        handled_message.handled_at,
    )
