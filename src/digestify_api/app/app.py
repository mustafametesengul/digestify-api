import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from digestify_api import identity, stories
from digestify_api.app.settings import AppSettings
from digestify_api.infrastructure import MessageBroker, StreamConsumer

settings = AppSettings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await identity.database.init_pool()
    await stories.database.init_pool()

    message_broker = MessageBroker()
    consumer = StreamConsumer(message_broker)
    consumer.add_registry(stories.handler_registry, "stories")

    tasks = [
        asyncio.create_task(identity.outbox_publisher.run()),
        asyncio.create_task(consumer.run()),
    ]

    try:
        yield
    finally:
        for task in tasks:
            task.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)
        await identity.database.close_pool()
        await stories.database.close_pool()


def main() -> None:
    app = FastAPI(
        title="Digestify API",
        lifespan=lifespan,
        debug=settings.debug,
    )

    app.include_router(identity.router)

    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
