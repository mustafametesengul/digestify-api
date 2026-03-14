import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator, Self

from digestify_api.infrastructure import (
    Database,
    MessageBroker,
    MessageProcessor,
    MessageRouter,
    OutboxRelay,
)


class NewsContext:
    def __init__(
        self,
        database: Database,
        message_broker: MessageBroker,
        message_processor: MessageProcessor,
        outbox_relay: OutboxRelay,
    ) -> None:
        self._database = database
        self._message_broker = message_broker
        self._message_processor = message_processor
        self._outbox_relay = outbox_relay

    @property
    def database(self) -> Database:
        return self._database

    async def run(self) -> None:
        tasks = [
            self._message_processor.run(),
            self._outbox_relay.run(),
        ]
        await asyncio.gather(*tasks)

    @classmethod
    @asynccontextmanager
    async def open(
        cls, name: str, message_router: MessageRouter
    ) -> AsyncIterator[Self]:
        async with (
            Database.open(schema=name) as database,
            MessageBroker.open() as message_broker,
        ):
            message_router.set_name(name)

            outbox_relay = OutboxRelay(
                database=database,
                message_broker=message_broker,
            )

            message_processor = MessageProcessor(
                message_broker=message_broker,
                message_router=message_router,
            )

            yield cls(
                database=database,
                message_broker=message_broker,
                message_processor=message_processor,
                outbox_relay=outbox_relay,
            )
