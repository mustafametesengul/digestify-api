import uuid
from datetime import datetime, timezone

from asyncpg import Connection

from digestify_api.models import SubscriptionTier, User
from digestify_api.queries import (
    create_user,
    increment_created_topics_count,
    increment_followed_topics_count,
    read_user,
    update_user,
    user_exists,
)


async def test_create_and_read_user(connection: Connection):
    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    user = User(
        id=user_id,
        discarded=False,
        subscription_tier=SubscriptionTier.FREE,
        created_topics_count=0,
        followed_topics_count=0,
        created_at=now,
        updated_at=None,
    )

    await create_user(connection, user)

    user_read = await read_user(connection, user_id)
    assert user_read is not None
    assert user_read.id == user_id
    assert user_read.discarded is False
    assert user_read.subscription_tier == SubscriptionTier.FREE
    assert user_read.created_topics_count == 0
    assert user_read.followed_topics_count == 0


async def test_update_user(connection: Connection):
    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    user = User(
        id=user_id,
        discarded=False,
        subscription_tier=SubscriptionTier.FREE,
        created_topics_count=0,
        followed_topics_count=0,
        created_at=now,
        updated_at=None,
    )
    await create_user(connection, user)

    user = User(
        id=user.id,
        discarded=True,
        subscription_tier=SubscriptionTier.PREMIUM,
        created_topics_count=5,
        followed_topics_count=10,
        created_at=user.created_at,
        updated_at=now,
    )
    await update_user(connection, user)

    user = await read_user(connection, user.id)
    assert user is not None
    assert user.discarded is True
    assert user.subscription_tier == SubscriptionTier.PREMIUM
    assert user.created_topics_count == 5
    assert user.followed_topics_count == 10


async def test_counters_increment(connection: Connection):
    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    user = User(
        id=user_id,
        discarded=False,
        subscription_tier=SubscriptionTier.FREE,
        created_topics_count=0,
        followed_topics_count=0,
        created_at=now,
        updated_at=None,
    )
    await create_user(connection, user)

    await increment_created_topics_count(connection, user.id)
    await increment_followed_topics_count(connection, user.id)

    user_read = await read_user(connection, user.id)
    assert user_read is not None
    assert user_read.created_topics_count == 1
    assert user_read.followed_topics_count == 1


async def test_user_exists(connection: Connection):
    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    assert await user_exists(connection, user_id) is False

    user = User(
        id=user_id,
        discarded=False,
        subscription_tier=SubscriptionTier.FREE,
        created_topics_count=0,
        followed_topics_count=0,
        created_at=now,
        updated_at=None,
    )
    await create_user(connection, user)
    assert await user_exists(connection, user_id) is True
