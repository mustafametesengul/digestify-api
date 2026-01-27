import uuid
from datetime import datetime, timezone

from digestify_api.users import SubscriptionTier, User, UserRepository


async def test_create_and_read_user(user_repo: UserRepository):
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

    await user_repo.create_user(user)

    user_read = await user_repo.read_user(user_id)
    assert user_read is not None
    assert user_read.id == user_id
    assert user_read.discarded is False
    assert user_read.subscription_tier == SubscriptionTier.FREE
    assert user_read.created_topics_count == 0
    assert user_read.followed_topics_count == 0


async def test_update_user(user_repo: UserRepository):
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
    await user_repo.create_user(user)

    user = User(
        id=user.id,
        discarded=True,
        subscription_tier=SubscriptionTier.PREMIUM,
        created_topics_count=5,
        followed_topics_count=10,
        created_at=user.created_at,
        updated_at=now,
    )
    await user_repo.update_user(user)

    user = await user_repo.read_user(user.id)
    assert user is not None
    assert user.discarded is True
    assert user.subscription_tier == SubscriptionTier.PREMIUM
    assert user.created_topics_count == 5
    assert user.followed_topics_count == 10


async def test_counters_increment(user_repo: UserRepository):
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
    await user_repo.create_user(user)

    await user_repo.increment_created_topics_count(user.id)
    await user_repo.increment_followed_topics_count(user.id)

    user_read = await user_repo.read_user(user.id)
    assert user_read is not None
    assert user_read.created_topics_count == 1
    assert user_read.followed_topics_count == 1


async def test_user_exists(user_repo: UserRepository):
    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    assert await user_repo.user_exists(user_id) is False

    user = User(
        id=user_id,
        discarded=False,
        subscription_tier=SubscriptionTier.FREE,
        created_topics_count=0,
        followed_topics_count=0,
        created_at=now,
        updated_at=None,
    )
    await user_repo.create_user(user)
    assert await user_repo.user_exists(user_id) is True
