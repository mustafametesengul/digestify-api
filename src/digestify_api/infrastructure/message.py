from datetime import datetime
from uuid import UUID

from asyncpg import Connection
from pydantic import BaseModel


class Message(BaseModel):
    id: UUID
    channel: str
    type: str
    payload: str
    created_at: datetime
    scheduled_at: datetime
    producer: str | None = None
    version: int | None = None


async def create_messages_table(connection: Connection) -> None:
    await connection.execute(
        """
        CREATE TABLE messages (
            id UUID PRIMARY KEY,
            channel TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL,
            type TEXT NOT NULL,
            payload JSONB NOT NULL,
            scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL,
            producer TEXT,
            version INT
        );

        CREATE INDEX ix_messages_scheduled_at ON messages (scheduled_at);
        CREATE INDEX ix_messages_type ON messages (type);
        """
    )


async def create_message(conn: Connection, message: Message) -> None:
    await conn.execute(
        """
        INSERT INTO messages
        (id, channel, type, payload, scheduled_at, created_at, producer, version)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """,
        message.id,
        message.channel,
        message.type,
        message.payload,
        message.scheduled_at,
        message.created_at,
        message.producer,
        message.version,
    )


migrations = [create_messages_table]
