import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from digestify_api import auth, stories
from digestify_api.app.settings import AppSettings

settings = AppSettings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await auth.database.init_pool()
    await stories.database.init_pool()

    tasks = [
        asyncio.create_task(auth.outbox_publisher.run()),
        asyncio.create_task(stories.stream_consumer.run()),
    ]

    try:
        yield
    finally:
        for task in tasks:
            task.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)
        await auth.database.close_pool()


def main() -> None:
    app = FastAPI(
        title="Digestify API",
        lifespan=lifespan,
        debug=settings.debug,
    )

    app.include_router(auth.router)

    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
