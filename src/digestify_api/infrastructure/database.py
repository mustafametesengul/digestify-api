from contextlib import asynccontextmanager
from typing import AsyncIterator

import asyncpg
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class DSNSettings(BaseSettings):
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


class PoolSettings(BaseSettings):
    min_size: int = Field(default=5)
    max_size: int = Field(default=20)
    command_timeout: int = Field(default=60)


def get_dsn(settings: DSNSettings) -> str:
    return (
        f"postgresql://"
        f"{settings.user}:{settings.password.get_secret_value()}"
        f"@{settings.host}:{settings.port}/{settings.db}"
    )


class Database:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[asyncpg.Connection]:
        async with self._pool.acquire() as connection:
            if not isinstance(connection, asyncpg.Connection):
                raise TypeError("Expected asyncpg.Connection from the pool")
            yield connection

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[asyncpg.Connection]:
        async with self.connection() as connection:
            async with connection.transaction():
                yield connection


@asynccontextmanager
async def create_database(
    dsn_settings: DSNSettings | None = None,
    pool_settings: PoolSettings | None = None,
    schema: str | None = None,
) -> AsyncIterator[Database]:
    dsn_settings = dsn_settings or DSNSettings()
    pool_settings = pool_settings or PoolSettings()
    dsn = get_dsn(dsn_settings)
    async with asyncpg.create_pool(
        dsn=dsn,
        min_size=pool_settings.min_size,
        max_size=pool_settings.max_size,
        command_timeout=pool_settings.command_timeout,
        server_settings={"search_path": schema} if schema else None,
    ) as pool:
        yield Database(pool)
