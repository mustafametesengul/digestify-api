import uuid
from datetime import datetime, timezone

from asyncpg import Connection

from digestify_api.models import user_models
from digestify_api.queries import user_queries


async def test_create_and_read_user(connection: Connection):
    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    user = user_models.User(
        id=user_id,
        discarded=False,
        tier=user_models.UserTier.FREE,
        created_topics_count=0,
        followed_topics_count=0,
        created_at=now,
        updated_at=None,
        username="user1",
        password_hash="",
    )

    await user_queries.create(connection, user)
    user_read = await user_queries.get(connection, user_id)
    assert user_read is not None
    assert user_read.id == user_id
    assert user_read.discarded is False
    assert user_read.tier == user_models.UserTier.FREE
    assert user_read.created_topics_count == 0
    assert user_read.followed_topics_count == 0


async def test_update_user(connection: Connection):
    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    user = user_models.User(
        id=user_id,
        discarded=False,
        tier=user_models.UserTier.FREE,
        created_topics_count=0,
        followed_topics_count=0,
        created_at=now,
        updated_at=None,
        username="user2",
        password_hash="",
    )
    await user_queries.create(connection, user)

    user = user_models.User(
        id=user.id,
        discarded=True,
        tier=user_models.UserTier.PREMIUM,
        created_topics_count=5,
        followed_topics_count=10,
        created_at=user.created_at,
        updated_at=now,
        username="user2",
        password_hash="",
    )
    await user_queries.update(connection, user)

    user = await user_queries.get(connection, user.id)
    assert user is not None
    assert user.discarded is True
    assert user.tier == user_models.UserTier.PREMIUM
    assert user.created_topics_count == 5
    assert user.followed_topics_count == 10


async def test_counters_increment(connection: Connection):
    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    user = user_models.User(
        id=user_id,
        discarded=False,
        tier=user_models.UserTier.FREE,
        created_topics_count=0,
        followed_topics_count=0,
        created_at=now,
        updated_at=None,
        username="user3",
        password_hash="",
    )
    await user_queries.create(connection, user)

    await user_queries.increment_created_topics_count(connection, user.id)
    await user_queries.increment_followed_topics_count(connection, user.id)

    user_read = await user_queries.get(connection, user.id)
    assert user_read is not None
    assert user_read.created_topics_count == 1
    assert user_read.followed_topics_count == 1


async def test_user_exists(connection: Connection):
    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    assert await user_queries.exists(connection, user_id) is False

    user = user_models.User(
        id=user_id,
        discarded=False,
        tier=user_models.UserTier.FREE,
        created_topics_count=0,
        followed_topics_count=0,
        created_at=now,
        updated_at=None,
        username="user4",
        password_hash="",
    )
    await user_queries.create(connection, user)
    assert await user_queries.exists(connection, user_id) is True
