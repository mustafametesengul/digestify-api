import uuid

import pytest

from digestify_api.models import SubscriptionTier, UserCreate, UserUpdate
from digestify_api.repositories.user_repository import UserRepository


@pytest.mark.asyncio
async def test_create_and_read_user(user_repo: UserRepository):
    user_id = uuid.uuid4()
    user_create = UserCreate(
        id=user_id,
        discarded=False,
        subscription_tier=SubscriptionTier.FREE,
        created_topics_count=0,
        followed_topics_count=0,
    )

    await user_repo.create_user(user_create)

    user_read = await user_repo.read_user(user_id)
    assert user_read is not None
    assert user_read.id == user_id
    assert user_read.discarded is False
    assert user_read.subscription_tier == SubscriptionTier.FREE
    assert user_read.created_topics_count == 0
    assert user_read.followed_topics_count == 0


@pytest.mark.asyncio
async def test_update_user(user_repo: UserRepository):
    user_id = uuid.uuid4()
    user_create = UserCreate(
        id=user_id,
        discarded=False,
        subscription_tier=SubscriptionTier.FREE,
        created_topics_count=0,
        followed_topics_count=0,
    )
    await user_repo.create_user(user_create)

    user_update = UserUpdate(
        id=user_id,
        discarded=True,
        subscription_tier=SubscriptionTier.PREMIUM,
        created_topics_count=5,
        followed_topics_count=10,
    )
    await user_repo.update_user(user_update)

    user_read = await user_repo.read_user(user_id)
    assert user_read is not None
    assert user_read.discarded is True
    assert user_read.subscription_tier == SubscriptionTier.PREMIUM
    assert user_read.created_topics_count == 5
    assert user_read.followed_topics_count == 10


@pytest.mark.asyncio
async def test_counters_increment(user_repo: UserRepository):
    user_id = uuid.uuid4()
    user_create = UserCreate(
        id=user_id,
        discarded=False,
        subscription_tier=SubscriptionTier.FREE,
        created_topics_count=0,
        followed_topics_count=0,
    )
    await user_repo.create_user(user_create)

    await user_repo.increase_created_topics_count(user_id)
    await user_repo.increase_followed_topics_count(user_id)

    user_read = await user_repo.read_user(user_id)
    assert user_read is not None
    assert user_read.created_topics_count == 1
    assert user_read.followed_topics_count == 1


@pytest.mark.asyncio
async def test_user_exists(user_repo: UserRepository):
    user_id = uuid.uuid4()
    assert await user_repo.user_exists(user_id) is False

    user_create = UserCreate(
        id=user_id,
        discarded=False,
        subscription_tier=SubscriptionTier.FREE,
        created_topics_count=0,
        followed_topics_count=0,
    )
    await user_repo.create_user(user_create)
    assert await user_repo.user_exists(user_id) is True


@pytest.mark.asyncio
async def test_is_user_discarded(user_repo: UserRepository):
    user_id = uuid.uuid4()
    # Non existent user should return False (as per implementation logic reading None -> False)
    assert await user_repo.is_user_discarded(user_id) is False

    user_create = UserCreate(
        id=user_id,
        discarded=True,
        subscription_tier=SubscriptionTier.FREE,
        created_topics_count=0,
        followed_topics_count=0,
    )
    await user_repo.create_user(user_create)
    assert await user_repo.is_user_discarded(user_id) is True
