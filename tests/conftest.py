from typing import AsyncIterator

import asyncpg
import pytest

from digestify_api import dependencies, entrypoints


@pytest.fixture(scope="session")
async def db() -> AsyncIterator[dependencies.db.DBManager]:
    settings = dependencies.db.DBSettings()
    manager = dependencies.db.DBManager(settings=settings)
    await manager.init_pool()

    await entrypoints.migrations.reset_db_(manager)
    await entrypoints.migrations.apply_migrations(manager)

    yield manager

    await entrypoints.migrations.reset_db_(manager)
    await manager.close_pool()


@pytest.fixture
async def connection(
    db: dependencies.db.DBManager,
) -> AsyncIterator[asyncpg.Connection]:
    async with db.get_connection() as connection:
        yield connection
