from typing import AsyncIterator

import asyncpg
import pytest

from digestify_api.db import DBService, DBSettings
from digestify_api.migrations import MigrationService
from digestify_api.stories import StoryRepository
from digestify_api.tasks import TaskRepository
from digestify_api.topics import TopicRepository
from digestify_api.users import UserRepository


@pytest.fixture(scope="session")
async def db_service() -> AsyncIterator[DBService]:
    settings = DBSettings()
    service = DBService(settings=settings)
    await service.init_pool()

    migrations_service = MigrationService(service)
    await migrations_service.apply_migrations()

    yield service

    await migrations_service.reset_db()
    await service.close_pool()


@pytest.fixture
async def connection(db_service: DBService) -> AsyncIterator[asyncpg.Connection]:
    async with db_service.get_connection() as connection:
        yield connection


@pytest.fixture
def user_repo(connection: asyncpg.Connection):
    return UserRepository(connection)


@pytest.fixture
def topic_repo(connection: asyncpg.Connection):
    return TopicRepository(connection)


@pytest.fixture
def story_repo(connection: asyncpg.Connection):
    return StoryRepository(connection)


@pytest.fixture
def task_repo(connection: asyncpg.Connection):
    return TaskRepository(connection)
