import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

import asyncpg

from digestify_api.db.settings import DBSettings


class DatabaseManager:
    def __init__(self, settings: DBSettings | None = None) -> None:
        if settings is None:
            settings = DBSettings()

        self._pool: asyncpg.Pool | None = None
        self._lock = asyncio.Lock()

        password = settings.password.get_secret_value()

        self._dsn: str = (
            f"postgresql://{settings.user}:{password}"
            f"@{settings.host}:{settings.port}/{settings.db}"
        )

    async def init_pool(self) -> None:
        async with self._lock:
            if self._pool is not None:
                return

            pool = await asyncpg.create_pool(
                dsn=self._dsn,
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
    async def get_connection(self) -> AsyncIterator[asyncpg.Connection]:
        if self._pool is None:
            raise RuntimeError(
                "Database pool is not initialized. Call init_pool first."
            )
        async with self._pool.acquire() as connection:
            if not isinstance(connection, asyncpg.Connection):
                raise RuntimeError("Failed to acquire a valid database connection.")
            async with connection.transaction():
                yield connection
