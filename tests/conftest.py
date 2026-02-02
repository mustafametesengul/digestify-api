from typing import AsyncIterator

import asyncpg
import pytest

from digestify_api.dependencies import db_manager
from digestify_api.entrypoints import migrations


@pytest.fixture(scope="session")
async def db() -> AsyncIterator[db_manager.DBManager]:
    settings = db_manager.DBSettings()
    manager = db_manager.DBManager(settings=settings)
    await manager.init_pool()

    await migrations.reset_db_(manager)
    await migrations.apply_migrations(manager)

    yield manager

    await migrations.reset_db_(manager)
    await manager.close_pool()


@pytest.fixture
async def connection(db: db_manager.DBManager) -> AsyncIterator[asyncpg.Connection]:
    async with db.get_connection() as connection:
        yield connection
