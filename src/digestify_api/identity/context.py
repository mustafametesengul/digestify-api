import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from digestify_api.identity.router import message_router
from digestify_api.identity.token_manager import TokenManager
from digestify_api.infrastructure import (
    Database,
    MessageBroker,
    MessageProcessor,
    OutboxRelay,
    create_database,
    create_message_broker,
)


class Context:
    def __init__(
        self,
        database: Database,
        message_broker: MessageBroker,
        outbox_relay: OutboxRelay,
        token_manager: TokenManager,
    ) -> None:
        self._database = database
        self._message_broker = message_broker
        self._outbox_relay = outbox_relay
        self._token_manager = token_manager

    @property
    def database(self) -> Database:
        return self._database

    @property
    def token_manager(self) -> TokenManager:
        return self._token_manager


@asynccontextmanager
async def create_context(name: str) -> AsyncIterator[Context]:
    async with (
        create_database(schema=name) as database,
        create_message_broker() as message_broker,
    ):
        message_router.set_name(name)

        outbox_relay = OutboxRelay(
            database=database,
            message_broker=message_broker,
        )

        token_manager = TokenManager()

        context = Context(
            database=database,
            message_broker=message_broker,
            outbox_relay=outbox_relay,
            token_manager=token_manager,
        )

        message_processor = MessageProcessor(
            context=context,
            message_broker=message_broker,
            message_router=message_router,
        )

        tasks = [
            asyncio.create_task(message_processor.run()),
            asyncio.create_task(outbox_relay.run()),
        ]

        yield context

        for task in tasks:
            task.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)
