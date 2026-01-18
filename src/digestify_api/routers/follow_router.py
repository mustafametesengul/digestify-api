from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from digestify_api.auth import Auth, get_auth
from digestify_api.exceptions import (
    FollowLimitExceeded,
    TopicNotFound,
    UserAlreadyFollowsTopic,
    UserDoesNotFollowTopic,
    UserNotFound,
)
from digestify_api.models import FollowCreate, FollowUpdate
from digestify_api.repositories import FollowRepository, TopicRepository, UserRepository

follow_router = APIRouter(
    prefix="/following",
    tags=["following"],
)


@follow_router.post("/follow")
async def follow(
    auth: Annotated[Auth, Depends(get_auth)],
    user_repository: Annotated[UserRepository, Depends()],
    topic_repository: Annotated[TopicRepository, Depends()],
    follow_repository: Annotated[FollowRepository, Depends()],
    topic_id: UUID,
) -> None:
    user = await user_repository.read_user(auth.id, lock=True)
    if user is None:
        raise UserNotFound()

    topic = await topic_repository.read_topic(topic_id)
    if topic is None:
        raise TopicNotFound()

    if user.followed_topics_count >= 50:
        raise FollowLimitExceeded(
            detail="User has reached the maximum number of followed topics."
        )

    follow_read = await follow_repository.read_follow(auth.id, topic_id, lock=True)
    if follow_read is not None and follow_read.is_following:
        raise UserAlreadyFollowsTopic()

    if follow_read is None:
        follow_create = FollowCreate(
            user_id=auth.id,
            topic_id=topic_id,
            is_following=True,
        )
        await follow_repository.create_follow(follow_create)
    else:
        follow_update = FollowUpdate(
            user_id=auth.id,
            topic_id=topic_id,
            is_following=True,
        )
        await follow_repository.update_follow(follow_update)

    await topic_repository.increase_followers_count(topic_id)


@follow_router.post("/unfollow")
async def unfollow(
    auth: Annotated[Auth, Depends(get_auth)],
    user_repository: Annotated[UserRepository, Depends()],
    topic_repository: Annotated[TopicRepository, Depends()],
    follow_repository: Annotated[FollowRepository, Depends()],
    topic_id: UUID,
) -> None:
    user = await user_repository.read_user(auth.id, lock=True)
    if user is None:
        raise UserNotFound()

    topic = await topic_repository.read_topic(topic_id)
    if topic is None:
        raise TopicNotFound()

    follow = await follow_repository.read_follow(auth.id, topic_id, lock=True)
    if follow is None or not follow.is_following:
        raise UserDoesNotFollowTopic()

    follow_update = FollowUpdate(
        user_id=auth.id,
        topic_id=topic_id,
        is_following=False,
    )
    await follow_repository.update_follow(follow_update)

    await topic_repository.decrease_followers_count(topic_id)
