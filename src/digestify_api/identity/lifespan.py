from contextlib import asynccontextmanager
from typing import AsyncIterator

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from redis.asyncio import Redis

from digestify_api.identity.dependencies import Context
from digestify_api.identity.token_generation import TokenGenerator
from digestify_api.identity.token_verification import TokenVerifier

from digestify_api.infrastructure import EventStore


class DSNSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_prefix="REDIS_",
    )

    host: str = Field(default="localhost")
    port: int = Field(default=6379)
    password: SecretStr = Field(default=SecretStr("password"))
    db: str = Field(default="0")


@asynccontextmanager
async def lifespan() -> AsyncIterator[Context]:
    token_generator = TokenGenerator()
    token_verifier = TokenVerifier()
    settings = DSNSettings()

    async with Redis(
        host=settings.host,
        port=settings.port,
        password=settings.password.get_secret_value(),
        db=settings.db,
    ) as redis:
        user_event_store = EventStore(redis, namespace="users")

        context = Context(
            user_event_store=user_event_store,
            token_generator=token_generator,
            token_verifier=token_verifier,
        )

        yield context
