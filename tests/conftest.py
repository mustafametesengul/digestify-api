from typing import AsyncIterator

import asyncpg
import pytest

from digestify_api.core import DBManager, DBSettings
from digestify_api.entrypoints import apply_migrations, reset_db_


@pytest.fixture(scope="session")
async def db() -> AsyncIterator[DBManager]:
    settings = DBSettings()
    manager = DBManager(settings=settings)
    await manager.init_pool()

    await apply_migrations(manager)

    yield manager

    await reset_db_(manager)
    await manager.close_pool()


@pytest.fixture
async def connection(db: DBManager) -> AsyncIterator[asyncpg.Connection]:
    async with db.get_connection() as connection:
        yield connection
