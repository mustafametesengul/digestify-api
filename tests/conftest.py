from typing import AsyncIterator

import asyncpg
import pytest

from digestify_api.db import DatabaseManager, DBSettings
from digestify_api.migrations import apply_migrations, reset_db_


@pytest.fixture(scope="session")
async def db_service() -> AsyncIterator[DatabaseManager]:
    settings = DBSettings()
    service = DatabaseManager(settings=settings)
    await service.init_pool()

    await apply_migrations(service)

    yield service

    await reset_db_(service)
    await service.close_pool()


@pytest.fixture
async def connection(db_service: DatabaseManager) -> AsyncIterator[asyncpg.Connection]:
    async with db_service.get_connection() as connection:
        yield connection
