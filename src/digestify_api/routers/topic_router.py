from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from digestify_api.auth import Auth, get_auth
from digestify_api.db import DBService, get_db
from digestify_api.exceptions.topic_exceptions import (
    TopicAlreadyExists,
    TopicLimitExceeded,
)
from digestify_api.exceptions.user_exceptions import UserNotFound
from digestify_api.queries.follow_queries import Follow, create_follow
from digestify_api.queries.topic_queries import (
    Topic,
    create_topic,
    topic_exists,
)
from digestify_api.queries.user_queries import (
    SubscriptionTier,
    increment_created_topics_count,
    read_user,
)

topic_router = APIRouter(
    prefix="/topic",
    tags=["topic"],
)


@topic_router.post("/create", status_code=201)
async def create(
    auth: Annotated[Auth, Depends(get_auth)],
    db: Annotated[DBService, Depends(get_db)],
    user_id: UUID,
    topic_id: UUID,
    name: str,
    description: str,
    language: str,
    image_url: str | None = None,
) -> None:
    now = datetime.now(timezone.utc)

    async with db.get_connection() as connection:
        user = await read_user(connection, user_id)
        if user is None:
            raise UserNotFound()

        topic_exists_flag = await topic_exists(connection, topic_id)
        if topic_exists_flag:
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

        await increment_created_topics_count(connection, user_id)

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

        await create_topic(connection, topic)

        follow = Follow(
            user_id=user_id,
            topic_id=topic_id,
            is_following=True,
            created_at=now,
            updated_at=None,
        )

        await create_follow(connection, follow)
