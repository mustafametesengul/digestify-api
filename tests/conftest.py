from typing import AsyncIterator

import asyncpg
import pytest

from digestify_api.db import DBSettings
from digestify_api.migrations import apply_migrations, reset_migrations
from digestify_api.repositories import (
    FollowRepository,
    StoryRepository,
    TopicRepository,
    UserRepository,
)


@pytest.fixture(scope="session")
def db_settings():
    return DBSettings()


@pytest.fixture
async def connection(
    db_settings: DBSettings,
) -> AsyncIterator[asyncpg.Connection]:
    conn: asyncpg.Connection = await asyncpg.connect(
        user=db_settings.user,
        password=db_settings.password,
        database=db_settings.db,
        host=db_settings.host,
        port=db_settings.port,
    )

    await reset_migrations(conn)
    await apply_migrations(conn)

    yield conn

    await reset_migrations(conn)
    await conn.close()


@pytest.fixture
def user_repo(connection: asyncpg.Connection):
    return UserRepository(connection)


@pytest.fixture
def topic_repo(connection: asyncpg.Connection):
    return TopicRepository(connection)


@pytest.fixture
def follow_repo(connection: asyncpg.Connection):
    return FollowRepository(connection)


@pytest.fixture
def story_repo(connection: asyncpg.Connection):
    return StoryRepository(connection)
