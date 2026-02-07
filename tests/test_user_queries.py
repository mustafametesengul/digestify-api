import uuid
from datetime import datetime, timezone

from asyncpg import Connection

from digestify_api import models, queries


async def test_create_and_read_user(connection: Connection):
    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    user = models.users.User(
        id=user_id,
        discarded=False,
        tier=models.users.UserTier.FREE,
        created_topics_count=0,
        followed_topics_count=0,
        active_topics_count=0,
        created_at=now,
        updated_at=None,
        username="user1",
        password_hash="",
        tier_last_confirmed_at=None,
    )

    await queries.users.create(connection, user)
    user_read = await queries.users.get(connection, user_id)
    assert user_read is not None
    assert user_read.id == user_id
    assert user_read.discarded is False
    assert user_read.tier == models.users.UserTier.FREE
    assert user_read.created_topics_count == 0
    assert user_read.followed_topics_count == 0


async def test_update_user(connection: Connection):
    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    user = models.users.User(
        id=user_id,
        discarded=False,
        tier=models.users.UserTier.FREE,
        created_topics_count=0,
        followed_topics_count=0,
        active_topics_count=0,
        created_at=now,
        updated_at=None,
        username="user2",
        password_hash="",
        tier_last_confirmed_at=None,
    )
    await queries.users.create(connection, user)

    user = models.users.User(
        id=user.id,
        discarded=True,
        tier=models.users.UserTier.PREMIUM,
        created_topics_count=5,
        followed_topics_count=10,
        active_topics_count=5,
        created_at=user.created_at,
        updated_at=now,
        username="user2",
        password_hash="",
        tier_last_confirmed_at=None,
    )
    await queries.users.update(connection, user)

    user = await queries.users.get(connection, user.id)
    assert user is not None
    assert user.discarded is True
    assert user.tier == models.users.UserTier.PREMIUM
    assert user.created_topics_count == 5
    assert user.followed_topics_count == 10
    assert user.active_topics_count == 5


async def test_counters_increment(connection: Connection):
    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    user = models.users.User(
        id=user_id,
        discarded=False,
        tier=models.users.UserTier.FREE,
        created_topics_count=0,
        followed_topics_count=0,
        active_topics_count=0,
        created_at=now,
        updated_at=None,
        username="user3",
        password_hash="",
        tier_last_confirmed_at=None,
    )
    await queries.users.create(connection, user)

    await queries.users.increment_created_topics_count(connection, user.id)
    await queries.users.increment_followed_topics_count(connection, user.id)

    user_read = await queries.users.get(connection, user.id)
    assert user_read is not None
    assert user_read.created_topics_count == 1
    assert user_read.followed_topics_count == 1


async def test_user_exists(connection: Connection):
    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    assert await queries.users.exists(connection, user_id) is False

    user = models.users.User(
        id=user_id,
        discarded=False,
        tier=models.users.UserTier.FREE,
        created_topics_count=0,
        followed_topics_count=0,
        active_topics_count=0,
        created_at=now,
        updated_at=None,
        username="user4",
        password_hash="",
        tier_last_confirmed_at=None,
    )
    await queries.users.create(connection, user)
    assert await queries.users.exists(connection, user_id) is True
