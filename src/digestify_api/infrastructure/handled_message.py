from datetime import UTC, datetime
from uuid import UUID

from asyncpg import Connection
from pydantic import BaseModel, Field


class HandledMessage(BaseModel):
    message_id: UUID
    handler_name: str
    handled_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


async def create_handled_messages_table(connection: Connection) -> None:
    await connection.execute(
        """
        CREATE TABLE handled_messages (
            message_id UUID NOT NULL,
            handler_name TEXT NOT NULL,
            handled_at TIMESTAMP WITH TIME ZONE NOT NULL,
            PRIMARY KEY (message_id, handler_name)
        );

        CREATE INDEX ix_handled_messages_handled_at ON handled_messages (handled_at);
        """
    )


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


migrations = [create_handled_messages_table]
