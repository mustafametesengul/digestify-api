import uuid

import pytest

from digestify_api.models import SubscriptionTier, TopicCreate, UserCreate
from digestify_api.repositories.topic_repository import TopicRepository
from digestify_api.repositories.user_repository import UserRepository


@pytest.fixture
async def associated_user_id(user_repo: UserRepository) -> uuid.UUID:
    user_id = uuid.uuid4()
    user = UserCreate(
        id=user_id,
        discarded=False,
        subscription_tier=SubscriptionTier.FREE,
        created_topics_count=0,
        followed_topics_count=0,
    )
    await user_repo.create_user(user)
    return user_id


@pytest.mark.asyncio
async def test_create_and_read_topic(
    topic_repo: TopicRepository, associated_user_id: uuid.UUID
):
    topic_id = uuid.uuid4()
    topic_create = TopicCreate(
        id=topic_id,
        discarded=False,
        user_id=associated_user_id,
        name="Test Topic",
        description="A test topic",
        language="en",
        image_url="http://example.com/image.png",
        is_active=True,
        followers_count=0,
    )

    await topic_repo.create_topic(topic_create)

    topic_read = await topic_repo.read_topic(topic_id)
    assert topic_read is not None
    assert topic_read.id == topic_id
    assert topic_read.name == "Test Topic"
    assert topic_read.user_id == associated_user_id


@pytest.mark.asyncio
async def test_topic_exists(topic_repo: TopicRepository, associated_user_id: uuid.UUID):
    topic_id = uuid.uuid4()
    assert await topic_repo.topic_exists(topic_id) is False

    topic_create = TopicCreate(
        id=topic_id,
        discarded=False,
        user_id=associated_user_id,
        name="Test Topic",
        description="A test topic",
        language="en",
        image_url=None,
        is_active=True,
        followers_count=0,
    )
    await topic_repo.create_topic(topic_create)
    assert await topic_repo.topic_exists(topic_id) is True


@pytest.mark.asyncio
async def test_is_topic_discarded(
    topic_repo: TopicRepository, associated_user_id: uuid.UUID
):
    topic_id = uuid.uuid4()
    # Non existent topic
    assert await topic_repo.is_topic_discarded(topic_id) is False

    topic_create = TopicCreate(
        id=topic_id,
        discarded=True,
        user_id=associated_user_id,
        name="Discarded Topic",
        description="...",
        language="en",
        image_url=None,
        is_active=True,
        followers_count=0,
    )
    await topic_repo.create_topic(topic_create)
    assert await topic_repo.is_topic_discarded(topic_id) is True


@pytest.mark.asyncio
async def test_update_followers_count(
    topic_repo: TopicRepository, associated_user_id: uuid.UUID
):
    topic_id = uuid.uuid4()
    topic_create = TopicCreate(
        id=topic_id,
        discarded=False,
        user_id=associated_user_id,
        name="Social Topic",
        description="...",
        language="en",
        image_url=None,
        is_active=True,
        followers_count=10,
    )
    await topic_repo.create_topic(topic_create)

    await topic_repo.increase_followers_count(topic_id)
    topic_read = await topic_repo.read_topic(topic_id)
    assert topic_read is not None
    assert topic_read.followers_count == 11

    await topic_repo.decrease_followers_count(topic_id)
    topic_read = await topic_repo.read_topic(topic_id)
    assert topic_read is not None
    assert topic_read.followers_count == 10
