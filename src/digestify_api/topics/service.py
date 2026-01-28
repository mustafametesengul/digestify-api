from datetime import datetime, timezone
from uuid import UUID

from digestify_api.db import DBService
from digestify_api.topics.exceptions import (
    FollowLimitExceeded,
    TopicAlreadyExists,
    TopicLimitExceeded,
    TopicNotFound,
    UserAlreadyFollowsTopic,
    UserDoesNotFollowTopic,
)
from digestify_api.topics.models import Follow, Topic
from digestify_api.topics.repository import TopicRepository
from digestify_api.users import SubscriptionTier, UserNotFound, UserRepository
from digestify import Digestify, Topic as DigestifyTopic
from digestify_api.stories import Story, StoryRepository


class TopicService:
    def __init__(
        self,
        db: DBService,
        digestify: Digestify,
    ) -> None:
        self._db = db
        self._digestify = digestify

    async def create_topic(
        self,
        user_id: UUID,
        topic_id: UUID,
        name: str,
        description: str,
        language: str,
        image_url: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc)

        async with self._db.get_connection() as connection:
            user_repository = UserRepository(connection)
            topic_repository = TopicRepository(connection)
            user = await user_repository.read_user(user_id)
            if user is None:
                raise UserNotFound()

            topic_exists = await topic_repository.topic_exists(topic_id)
            if topic_exists:
                raise TopicAlreadyExists()

            if user.subscription_tier is SubscriptionTier.FREE:
                raise TopicLimitExceeded(
                    detail=(
                        "Free tier users cannot create topics. "
                        "Please upgrade your subscription to create topics."
                    )
                )

            if (
                user.created_topics_count >= 10
                and user.subscription_tier is SubscriptionTier.PREMIUM
            ):
                raise TopicLimitExceeded(
                    detail=(
                        "Premium tier users can create up to 10 topics. "
                        "Please delete some topics to create new ones."
                    )
                )

            await user_repository.increment_created_topics_count(user_id)

            topic = Topic(
                id=topic_id,
                user_id=user_id,
                discarded=False,
                image_url=image_url,
                is_active=True,
                name=name,
                description=description,
                language=language,
                followers_count=1,
                created_at=now,
                updated_at=None,
            )

            await topic_repository.create_topic(topic)

            follow = Follow(
                user_id=user_id,
                topic_id=topic_id,
                is_following=True,
                created_at=now,
                updated_at=None,
            )

            await topic_repository.create_follow(follow)

    async def follow(
        self,
        user_id: UUID,
        topic_id: UUID,
    ) -> None:
        now = datetime.now(timezone.utc)

        async with self._db.get_connection() as connection:
            user_repository = UserRepository(connection)
            topic_repository = TopicRepository(connection)

            user = await user_repository.read_user(user_id)
            if user is None:
                raise UserNotFound()

            topic = await topic_repository.read_topic(topic_id)
            if topic is None:
                raise TopicNotFound()

            if user.followed_topics_count >= 50:
                raise FollowLimitExceeded(
                    detail="User has reached the maximum number of followed topics."
                )

            follow = await topic_repository.read_follow(user_id, topic_id, lock=True)

            if follow is None:
                follow = Follow(
                    user_id=user_id,
                    topic_id=topic_id,
                    is_following=True,
                    created_at=now,
                    updated_at=None,
                )
                await topic_repository.create_follow(follow)
            else:
                if follow.is_following:
                    raise UserAlreadyFollowsTopic()

                follow.is_following = True
                follow.updated_at = now

                await topic_repository.update_follow(follow)

            await topic_repository.increment_followers_count(topic_id)

    async def unfollow(
        self,
        user_id: UUID,
        topic_id: UUID,
    ) -> None:
        now = datetime.now(timezone.utc)
        async with self._db.get_connection() as connection:
            user_repository = UserRepository(connection)
            topic_repository = TopicRepository(connection)

            user = await user_repository.read_user(user_id, lock=True)
            if user is None:
                raise UserNotFound()

            topic = await topic_repository.read_topic(topic_id)
            if topic is None:
                raise TopicNotFound()

            follow = await topic_repository.read_follow(user_id, topic_id, lock=True)
            if follow is None or not follow.is_following:
                raise UserDoesNotFollowTopic()

            follow.is_following = False
            follow.updated_at = now

            await topic_repository.update_follow(follow)
            await topic_repository.decrement_followers_count(topic_id)

            await user_repository.decrement_followed_topics_count(user_id)

    
    async def save_stories_by_topic(self, topic_id: UUID) -> None:
        now = datetime.now(timezone.utc)
        async with self._db.get_connection() as connection:
            topic_repository = TopicRepository(connection)
            topic = await topic_repository.read_topic(topic_id)
            if topic is None:
                raise TopicNotFound()

        digestify_topic = DigestifyTopic.model_validate(topic.model_dump())

        digest = await self._digestify.get_stories(digestify_topic)

        stories = [
            Story.model_validate(story.model_dump()) for story in digest.stories
        ]

        async with self._db.get_connection() as connection:
            story_repository = StoryRepository(connection)
            for story in stories:
                story_create = Story(
                    id=story.id,
                    discarded=False,
                    topic_id=topic_id,
                    title=story.title,
                    image_url=story.image_url,
                    content=story.content,
                    language=story.language,
                    created_at=now,
                    updated_at=None,
                )
                await story_repository.create_story(story_create)
