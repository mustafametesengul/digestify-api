import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from digestify_api.identity.context import Context
from digestify_api.identity.router import message_router
from digestify_api.identity.token_manager import TokenManager
from digestify_api.infrastructure import (
    MessageProcessor,
    OutboxRelay,
    create_database,
    create_message_broker,
)


@asynccontextmanager
async def lifespan(name: str) -> AsyncIterator[Context]:
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
