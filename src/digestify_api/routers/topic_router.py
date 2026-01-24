from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from digestify_api.auth import Auth, get_auth
from digestify_api.exceptions import (
    TopicAlreadyExists,
    TopicLimitExceeded,
    UserNotFound,
)
from digestify_api.models import FollowCreate, SubscriptionTier, TopicCreate
from digestify_api.repositories import FollowRepository, TopicRepository, UserRepository

topic_router = APIRouter(
    prefix="/topic",
    tags=["topic"],
)


@topic_router.post("/create", status_code=201)
async def create_topic(
    auth: Annotated[Auth, Depends(get_auth)],
    user_repository: Annotated[UserRepository, Depends()],
    topic_repository: Annotated[TopicRepository, Depends()],
    follow_repository: Annotated[FollowRepository, Depends()],
    topic_id: UUID,
    name: str,
    description: str,
    language: str,
    image_url: str | None = None,
) -> None:
    user_read = await user_repository.read_user(auth.id, lock=True)
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
        user_id=auth.id,
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
        user_id=auth.id,
        topic_id=topic_id,
        is_following=True,
    )

    await follow_repository.create_follow(follow_create)
