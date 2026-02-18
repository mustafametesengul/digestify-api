from datetime import datetime
from uuid import UUID

from asyncpg import Connection

from digestify_api.messaging.models import Message


async def create_messaging_tables(connection: Connection) -> None:
    await connection.execute(
        """
        CREATE TABLE messages (
            id UUID PRIMARY KEY,
            channel TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL,
            type TEXT NOT NULL,
            payload JSONB NOT NULL,
            scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL
        );

        CREATE INDEX ix_messages_scheduled_at ON messages (scheduled_at);
        CREATE INDEX ix_messages_type ON messages (type);

        CREATE TABLE outbox (
            id UUID PRIMARY KEY,
            channel TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL,
            type TEXT NOT NULL,
            payload JSONB NOT NULL,
            scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL
        );

        CREATE INDEX ix_outbox_scheduled_at ON outbox (scheduled_at);
        CREATE INDEX ix_outbox_type ON outbox (type);

        CREATE TABLE handled_messages (
            message_id UUID NOT NULL,
            handler_name TEXT NOT NULL,
            handled_at TIMESTAMP WITH TIME ZONE NOT NULL,
            PRIMARY KEY (message_id, handler_name)
        );

        CREATE INDEX ix_handled_messages_handled_at ON handled_messages (handled_at);
        """
    )


async def create_message(conn: Connection, message: Message) -> None:
    await conn.execute(
        """
        INSERT INTO messages
        (id, channel, type, payload, scheduled_at, created_at)
        VALUES ($1, $2, $3, $4, $5, $6)
        """,
        message.id,
        message.destination,
        message.type,
        message.payload,
        message.scheduled_at,
        message.created_at,
    )
    await conn.execute(
        """
        INSERT INTO outbox
        (id, channel, type, payload, scheduled_at, created_at)
        VALUES ($1, $2, $3, $4, $5, $6)
        """,
        message.id,
        message.destination,
        message.type,
        message.payload,
        message.scheduled_at,
        message.created_at,
    )


async def get_outbox_messages(
    conn: Connection,
    time: datetime,
    limit: int,
) -> list[Message]:
    rows = await conn.fetch(
        """
        SELECT *
        FROM outbox
        WHERE scheduled_at <= $1
        ORDER BY scheduled_at ASC
        FOR UPDATE SKIP LOCKED
        LIMIT $2
        """,
        time,
        limit,
    )
    return [Message.model_validate(dict(row)) for row in rows]


async def delete_outbox_message(conn: Connection, message_id: UUID) -> None:
    await conn.execute(
        """
        DELETE FROM outbox
        WHERE id = $1
        """,
        message_id,
    )


async def add_channel_column(connection: Connection) -> None:
    await connection.execute(
        """
        ALTER TABLE messages
        ADD COLUMN IF NOT EXISTS channel TEXT NOT NULL DEFAULT 'default';
        """
    )
    await connection.execute(
        """
        ALTER TABLE outbox
        ADD COLUMN IF NOT EXISTS channel TEXT NOT NULL DEFAULT 'default';
        """
    )
