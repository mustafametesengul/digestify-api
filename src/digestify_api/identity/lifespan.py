from contextlib import asynccontextmanager
from typing import AsyncIterator

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import nats

from digestify_api.identity.dependencies import Context
from digestify_api.identity.token_generation import TokenGenerator
from digestify_api.identity.token_verification import TokenVerifier

from digestify_api.infrastructure import EventStore


class DSNSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_prefix="NATS_",
    )

    host: str = Field(default="localhost")
    port: int = Field(default=4222)


@asynccontextmanager
async def lifespan() -> AsyncIterator[Context]:
    token_generator = TokenGenerator()
    token_verifier = TokenVerifier()
    settings = DSNSettings()

    nc = await nats.connect(f"nats://{settings.host}:{settings.port}")
    try:
        js = nc.jetstream()
        await js.add_stream(name="identity", subjects=["users.*"])

        event_store = EventStore(js)

        context = Context(
            event_store=event_store,
            token_generator=token_generator,
            token_verifier=token_verifier,
        )

        yield context
    finally:
        await nc.close()
