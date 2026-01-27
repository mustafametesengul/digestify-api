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
from digestify_api.topics.models import FollowCreate, FollowUpdate, TopicCreate
from digestify_api.topics.repository import TopicRepository
from digestify_api.users import SubscriptionTier, UserNotFound, UserRepository


class TopicService:
    def __init__(
        self,
        db: DBService,
    ) -> None:
        self._db = db

    async def create_topic(
        self,
        user_id: UUID,
        topic_id: UUID,
        name: str,
        description: str,
        language: str,
        image_url: str | None = None,
    ) -> None:
        async with self._db.get_connection() as connection:
            user_repository = UserRepository(connection)
            topic_repository = TopicRepository(connection)
            user_read = await user_repository.read_user(user_id, lock=True)
            if user_read is None:
                raise UserNotFound()

            topic_exists = await topic_repository.topic_exists(topic_id)
            if topic_exists:
                raise TopicAlreadyExists()

            if user_read.subscription_tier is SubscriptionTier.FREE:
                raise TopicLimitExceeded(
                    detail=(
                        "Free tier users cannot create topics. "
                        "Please upgrade your subscription to create topics."
                    )
                )

            if (
                user_read.created_topics_count >= 10
                and user_read.subscription_tier is SubscriptionTier.PREMIUM
            ):
                raise TopicLimitExceeded(
                    detail=(
                        "Premium tier users can create up to 10 topics. "
                        "Please delete some topics to create new ones."
                    )
                )

            topic_create = TopicCreate(
                id=topic_id,
                user_id=user_id,
                discarded=False,
                image_url=image_url,
                is_active=True,
                name=name,
                description=description,
                language=language,
                followers_count=1,
            )

            await topic_repository.create_topic(topic_create)

            follow_create = FollowCreate(
                user_id=user_id,
                topic_id=topic_id,
                is_following=True,
            )

            await topic_repository.create_follow(follow_create)

    async def follow(
        self,
        user_id: UUID,
        topic_id: UUID,
    ) -> None:
        async with self._db.get_connection() as connection:
            user_repository = UserRepository(connection)
            topic_repository = TopicRepository(connection)

            user = await user_repository.read_user(user_id, lock=True)
            if user is None:
                raise UserNotFound()

            topic = await topic_repository.read_topic(topic_id)
            if topic is None:
                raise TopicNotFound()

            if user.followed_topics_count >= 50:
                raise FollowLimitExceeded(
                    detail="User has reached the maximum number of followed topics."
                )

            follow_read = await topic_repository.read_follow(
                user_id, topic_id, lock=True
            )
            if follow_read is not None and follow_read.is_following:
                raise UserAlreadyFollowsTopic()

            if follow_read is None:
                follow_create = FollowCreate(
                    user_id=user_id,
                    topic_id=topic_id,
                    is_following=True,
                )
                await topic_repository.create_follow(follow_create)
            else:
                follow_update = FollowUpdate(
                    user_id=user_id,
                    topic_id=topic_id,
                    is_following=True,
                )
                await topic_repository.update_follow(follow_update)

            await topic_repository.increase_followers_count(topic_id)

    async def unfollow(
        self,
        user_id: UUID,
        topic_id: UUID,
    ) -> None:
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

            follow_update = FollowUpdate(
                user_id=user_id,
                topic_id=topic_id,
                is_following=False,
            )
            await topic_repository.update_follow(follow_update)

            await topic_repository.decrease_followers_count(topic_id)
