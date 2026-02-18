import asyncio
from datetime import datetime, timezone

from redis.asyncio import Redis

from digestify_api.db import Database
from digestify_api.messaging.models import Message
from digestify_api.messaging.queries import delete_outbox_message, get_outbox_messages


class OutboxRelay:
    def __init__(
        self,
        database: Database,
        batch_size: int = 10,
        poll_interval: float = 1.0,
    ) -> None:
        self._database = database
        self._redis = Redis(password="password")
        self._stream = database.schema
        self._batch_size = batch_size
        self._poll_interval = poll_interval

    async def _publish(self, message: Message) -> None:
        await self._redis.xadd(
            name=self._stream,
            fields={"message": message.model_dump_json()},
        )

    async def run(self) -> None:
        while True:
            now = datetime.now(timezone.utc)
            async with self._database.transaction() as connection:
                messages = await get_outbox_messages(
                    connection,
                    now,
                    limit=self._batch_size,
                )
                print(f"Found {len(messages)} pending messages")
                for message in messages:
                    await self._publish(message)
                    await delete_outbox_message(connection, message.id)
            await asyncio.sleep(self._poll_interval)
