import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator, Self

from fastapi import Request

from digestify_api.infrastructure import (
    Database,
    MessageBroker,
    MessageProcessor,
    OperationRegistry,
    OutboxRelay,
)


class IdentityContext:
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
        cls, name: str, registries: list[OperationRegistry]
    ) -> AsyncIterator[Self]:
        async with (
            Database.open(schema=name) as database,
            MessageBroker.open() as message_broker,
        ):
            outbox_relay = OutboxRelay(
                database=database,
                message_broker=message_broker,
            )
            yield cls(
                database=database,
                message_broker=message_broker,
                message_processor=MessageProcessor(message_broker, registries),
                outbox_relay=outbox_relay,
            )


def get_context(request: Request) -> IdentityContext:
    return request.app.state.identity_context
