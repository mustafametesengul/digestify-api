import uuid

import pytest

from digestify_api.models import StoryCreate, SubscriptionTier, TopicCreate, UserCreate
from digestify_api.repositories.story_repository import StoryRepository
from digestify_api.repositories.topic_repository import TopicRepository
from digestify_api.repositories.user_repository import UserRepository


@pytest.fixture
async def associated_topic_id(
    user_repo: UserRepository, topic_repo: TopicRepository
) -> uuid.UUID:
    user_id = uuid.uuid4()
    user = UserCreate(
        id=user_id,
        discarded=False,
        subscription_tier=SubscriptionTier.FREE,
        created_topics_count=0,
        followed_topics_count=0,
    )
    await user_repo.create_user(user)

    topic_id = uuid.uuid4()
    topic = TopicCreate(
        id=topic_id,
        discarded=False,
        user_id=user_id,
        name="Test Topic",
        description="A test topic",
        language="en",
        image_url=None,
        is_active=True,
        followers_count=0,
    )
    await topic_repo.create_topic(topic)
    return topic_id


@pytest.mark.asyncio
async def test_create_and_read_story(
    story_repo: StoryRepository, associated_topic_id: uuid.UUID
):
    story_id = uuid.uuid4()
    story_create = StoryCreate(
        id=story_id,
        discarded=False,
        topic_id=associated_topic_id,
        title="Test Story",
        image_url="http://example.com/image.png",
        content="This is the content of the story.",
        language="en",
    )

    await story_repo.create_story(story_create)

    story_read = await story_repo.read_story(story_id)
    assert story_read is not None
    assert story_read.id == story_id
    assert story_read.title == "Test Story"
    assert story_read.topic_id == associated_topic_id
    assert story_read.created_at is not None
    assert story_read.updated_at is not None


@pytest.mark.asyncio
async def test_story_exists(
    story_repo: StoryRepository, associated_topic_id: uuid.UUID
):
    story_id = uuid.uuid4()
    assert await story_repo.story_exists(story_id) is False

    story_create = StoryCreate(
        id=story_id,
        discarded=False,
        topic_id=associated_topic_id,
        title="Test Story",
        image_url=None,
        content="Content",
        language="en",
    )
    await story_repo.create_story(story_create)
    assert await story_repo.story_exists(story_id) is True


@pytest.mark.asyncio
async def test_is_story_discarded(
    story_repo: StoryRepository, associated_topic_id: uuid.UUID
):
    story_id = uuid.uuid4()
    # Non existent story
    assert await story_repo.is_story_discarded(story_id) is False

    story_create = StoryCreate(
        id=story_id,
        discarded=True,
        topic_id=associated_topic_id,
        title="Discarded Story",
        image_url=None,
        content="Content",
        language="en",
    )
    await story_repo.create_story(story_create)
    assert await story_repo.is_story_discarded(story_id) is True
