import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID

from asyncpg import Connection

from digestify_api.infrastructure.database import Database
from digestify_api.infrastructure.message import Message
from digestify_api.infrastructure.message_broker import MessageBroker

_logger = logging.getLogger(__name__)


async def create_outbox_message(conn: Connection, message: Message) -> None:
    await conn.execute(
        """
        INSERT INTO outbox
        (id, channel, type, payload, scheduled_at, created_at)
        VALUES ($1, $2, $3, $4, $5, $6)
        """,
        message.id,
        message.channel,
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


class OutboxRelay:
    def __init__(
        self,
        database: Database,
        message_broker: MessageBroker,
        batch_size: int = 10,
        poll_interval: float = 1.0,
    ) -> None:
        self._database = database
        self._message_broker = message_broker
        self._batch_size = batch_size
        self._poll_interval = poll_interval

    async def run(self) -> None:
        try:
            while True:
                now = datetime.now(UTC)
                async with self._database.transaction() as connection:
                    messages = await get_outbox_messages(
                        connection,
                        now,
                        limit=self._batch_size,
                    )
                    for message in messages:
                        await self._message_broker.publish_message(message)
                        await delete_outbox_message(connection, message.id)
                await asyncio.sleep(self._poll_interval)
        except asyncio.CancelledError:
            raise
        except Exception:
            _logger.exception("OutboxRelay background task crashed")
            raise
