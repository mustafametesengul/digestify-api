import asyncio
from datetime import datetime, timezone

from digestify_api.infrastructure.database import Database
from digestify_api.infrastructure.message_broker import MessageBroker
from digestify_api.infrastructure.queries import (
    delete_outbox_message,
    get_outbox_messages,
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
                    await self._message_broker.publish_message(message)
                    await delete_outbox_message(connection, message.id)
            await asyncio.sleep(self._poll_interval)
