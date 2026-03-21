import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from digestify_api.identity.context import Context
from digestify_api.identity.migrations import migrations
from digestify_api.identity.router import message_router
from digestify_api.identity.token_decoder import TokenDecoder
from digestify_api.identity.token_generator import TokenGenerator
from digestify_api.infrastructure import (
    MessageProcessor,
    OutboxRelay,
    apply_migrations,
    create_database,
    create_message_broker,
)


@asynccontextmanager
async def lifespan(name: str) -> AsyncIterator[Context]:
    async with (
        create_database(schema=name) as database,
        create_message_broker() as message_broker,
    ):
        await apply_migrations(schema=name, migrations=migrations)

        message_router.set_name(name)

        outbox_relay = OutboxRelay(
            database=database,
            message_broker=message_broker,
        )

        token_generator = TokenGenerator()
        token_decoder = TokenDecoder()

        context = Context(
            database=database,
            token_generator=token_generator,
            token_decoder=token_decoder,
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
