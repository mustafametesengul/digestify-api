import uuid

import pytest

from digestify_api.models import (
    FollowCreate,
    FollowUpdate,
    SubscriptionTier,
    TopicCreate,
    UserCreate,
)
from digestify_api.repositories.follow_repository import FollowRepository
from digestify_api.repositories.topic_repository import TopicRepository
from digestify_api.repositories.user_repository import UserRepository


@pytest.fixture
async def setup_data(user_repo: UserRepository, topic_repo: TopicRepository):
    # Create user
    user_id = uuid.uuid4()
    user = UserCreate(
        id=user_id,
        discarded=False,
        subscription_tier=SubscriptionTier.FREE,
        created_topics_count=0,
        followed_topics_count=0,
    )
    await user_repo.create_user(user)

    # Create topic (owned by same user for simplicity, though could be different)
    topic_id = uuid.uuid4()
    topic = TopicCreate(
        id=topic_id,
        discarded=False,
        user_id=user_id,
        name="Test Topic",
        description="...",
        language="en",
        image_url=None,
        is_active=True,
        followers_count=0,
    )
    await topic_repo.create_topic(topic)

    return user_id, topic_id


@pytest.mark.asyncio
async def test_create_and_read_follow(follow_repo: FollowRepository, setup_data):
    user_id, topic_id = setup_data

    follow_create = FollowCreate(user_id=user_id, topic_id=topic_id, is_following=True)

    await follow_repo.create_follow(follow_create)

    follow_read = await follow_repo.read_follow(user_id, topic_id)
    assert follow_read is not None
    assert follow_read.user_id == user_id
    assert follow_read.topic_id == topic_id
    assert follow_read.is_following is True


@pytest.mark.asyncio
async def test_update_follow(follow_repo: FollowRepository, setup_data):
    user_id, topic_id = setup_data

    follow_create = FollowCreate(user_id=user_id, topic_id=topic_id, is_following=True)
    await follow_repo.create_follow(follow_create)

    follow_update = FollowUpdate(user_id=user_id, topic_id=topic_id, is_following=False)
    await follow_repo.update_follow(follow_update)

    follow_read = await follow_repo.read_follow(user_id, topic_id)
    assert follow_read is not None
    assert follow_read.is_following is False


@pytest.mark.asyncio
async def test_read_follow_not_found(follow_repo: FollowRepository):
    # Random UUIDs that don't exist
    assert await follow_repo.read_follow(uuid.uuid4(), uuid.uuid4()) is None
