import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

import asyncpg
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_prefix="POSTGRES_",
    )

    host: str = Field(default="localhost")
    port: int = Field(default=5432)
    user: str = Field(default="user")
    password: SecretStr = Field(default=SecretStr("password"))
    db: str = Field(default="db")


class Database:
    def __init__(
        self,
        settings: DatabaseSettings | None = None,
    ) -> None:
        self._pool: asyncpg.Pool | None = None
        self._lock = asyncio.Lock()
        self._settings = settings or DatabaseSettings()
        self._schema: str | None = None

    async def init_pool(self, schema: str | None = None) -> None:
        dsn = (
            f"postgresql://"
            f"{self._settings.user}:{self._settings.password.get_secret_value()}"
            f"@{self._settings.host}:{self._settings.port}/{self._settings.db}"
        )

        async with self._lock:
            self._schema = schema

            if self._pool is not None:
                return

            pool = await asyncpg.create_pool(
                dsn=dsn,
                min_size=5,
                max_size=20,
                command_timeout=60,
            )

            self._pool = pool

    async def close_pool(self) -> None:
        async with self._lock:
            if self._pool is not None:
                await self._pool.close()
                self._pool = None
                self._schema = None

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[asyncpg.Connection]:
        if self._pool is None or self._schema is None:
            raise RuntimeError(
                "Database pool is not initialized. Call init_pool first."
            )
        async with self._pool.acquire() as connection:
            if not isinstance(connection, asyncpg.Connection):
                raise RuntimeError("Failed to acquire a valid database connection.")
            await connection.execute(f"SET search_path TO {self._schema}")
            async with connection.transaction():
                yield connection
