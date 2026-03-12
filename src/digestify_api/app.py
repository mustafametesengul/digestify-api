import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from digestify_api import identity, infrastructure, topics


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_prefix="DIGESTIFY_API_",
    )

    debug: bool = Field(default=False)
    host: str = Field(default="localhost")
    port: int = Field(default=8000)


settings = AppSettings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await identity.database.connect("identity")
    await topics.database.connect("topics")

    await infrastructure.apply_migrations(identity.database, identity.migrations)
    await infrastructure.apply_migrations(topics.database, topics.migrations)

    message_broker = infrastructure.MessageBroker()
    message_processor = infrastructure.MessageProcessor(message_broker)
    message_processor.add_registry(topics.operation_registry, "topics")

    tasks = [
        asyncio.create_task(identity.outbox_relay.run()),
        asyncio.create_task(message_processor.run()),
    ]

    try:
        yield
    finally:
        for task in tasks:
            task.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)
        await identity.database.close()
        await topics.database.close()


def run_app() -> None:
    app = FastAPI(
        title="Digestify API",
        lifespan=lifespan,
        debug=settings.debug,
    )

    app.include_router(identity.router)

    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    run_app()
