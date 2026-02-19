import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

import asyncpg

from digestify_api.db.settings import DatabaseSettings


class Database:
    def __init__(
        self,
        settings: DatabaseSettings | None = None,
    ) -> None:
        self._pool: asyncpg.Pool | None = None
        self._lock = asyncio.Lock()
        self._settings = settings or DatabaseSettings()

    @property
    def schema(self) -> str:
        return self._settings.db_schema

    async def init_pool(self) -> None:
        dsn = (
            f"postgresql://"
            f"{self._settings.user}:{self._settings.password.get_secret_value()}"
            f"@{self._settings.host}:{self._settings.port}/{self._settings.db}"
        )
        async with self._lock:
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

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[asyncpg.Connection]:
        if self._pool is None:
            raise RuntimeError(
                "Database pool is not initialized. Call init_pool first."
            )
        async with self._pool.acquire() as connection:
            if not isinstance(connection, asyncpg.Connection):
                raise RuntimeError("Failed to acquire a valid database connection.")
            await connection.execute(f"SET search_path TO {self._settings.db_schema}")
            async with connection.transaction():
                yield connection
