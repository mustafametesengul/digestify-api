import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

import asyncpg
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DBSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_prefix="POSTGRES_",
    )

    host: str = Field(default="localhost")
    port: int = Field(default=5432)
    user: str = Field(default="user")
    password: str = Field(default="password")
    db: str = Field(default="db")


_pool: asyncpg.Pool | None = None
_pool_lock = asyncio.Lock()


async def create_pool(settings: DBSettings | None = None) -> None:
    global _pool

    async with _pool_lock:
        if _pool is not None:
            return

        if settings is None:
            settings = DBSettings()

        dsn = (
            f"postgresql://{settings.user}:{settings.password}"
            f"@{settings.host}:{settings.port}/{settings.db}"
        )

        _pool = await asyncpg.create_pool(
            dsn=dsn,
            min_size=5,
            max_size=20,
            command_timeout=60,
        )


async def close_pool() -> None:
    global _pool
    async with _pool_lock:
        if _pool is not None:
            await _pool.close()
            _pool = None


@asynccontextmanager
async def get_connection() -> AsyncIterator[asyncpg.Connection]:
    global _pool
    if _pool is None:
        raise RuntimeError("Database pool is not initialized. Call create_pool first.")
    async with _pool.acquire() as connection:
        if not isinstance(connection, asyncpg.Connection):
            raise RuntimeError("Failed to acquire a valid database connection.")
        async with connection.transaction():
            yield connection
