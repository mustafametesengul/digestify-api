from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from digestify_api.auth import Auth, get_auth
from digestify_api.db import DBService, get_db
from digestify_api.exceptions.follow_exceptions import (
    FollowLimitExceeded,
    UserAlreadyFollowsTopic,
    UserDoesNotFollowTopic,
)
from digestify_api.exceptions.topic_exceptions import (
    TopicNotFound,
)
from digestify_api.exceptions.user_exceptions import UserNotFound
from digestify_api.queries.follow_queries import (
    Follow,
    create_follow,
    read_follow,
    update_follow,
)
from digestify_api.queries.topic_queries import (
    decrement_followers_count,
    increment_followers_count,
    read_topic,
)
from digestify_api.queries.user_queries import (
    decrement_followed_topics_count,
    read_user,
)

follow_router = APIRouter(
    prefix="/follow",
    tags=["follow"],
)


@follow_router.post("/follow", status_code=200)
async def follow(
    auth: Annotated[Auth, Depends(get_auth)],
    db: Annotated[DBService, Depends(get_db)],
    user_id: UUID,
    topic_id: UUID,
) -> None:
    now = datetime.now(timezone.utc)

    async with db.get_connection() as connection:
        user = await read_user(connection, user_id)
        if user is None:
            raise UserNotFound()

        topic = await read_topic(connection, topic_id)
        if topic is None:
            raise TopicNotFound()

        if user.followed_topics_count >= 50:
            raise FollowLimitExceeded(
                detail="User has reached the maximum number of followed topics."
            )

        follow = await read_follow(connection, user_id, topic_id, lock=True)

        if follow is None:
            follow = Follow(
                user_id=user_id,
                topic_id=topic_id,
                is_following=True,
                created_at=now,
                updated_at=None,
            )
            await create_follow(connection, follow)
        else:
            if follow.is_following:
                raise UserAlreadyFollowsTopic()

            follow.is_following = True
            follow.updated_at = now

            await update_follow(connection, follow)

        await increment_followers_count(connection, topic_id)


@follow_router.post("/unfollow", status_code=200)
async def unfollow(
    auth: Annotated[Auth, Depends(get_auth)],
    db: Annotated[DBService, Depends(get_db)],
    user_id: UUID,
    topic_id: UUID,
) -> None:
    now = datetime.now(timezone.utc)
    async with db.get_connection() as connection:
        user = await read_user(connection, user_id, lock=True)
        if user is None:
            raise UserNotFound()

        topic = await read_topic(connection, topic_id)
        if topic is None:
            raise TopicNotFound()

        follow = await read_follow(connection, user_id, topic_id, lock=True)
        if follow is None or not follow.is_following:
            raise UserDoesNotFollowTopic()

        follow.is_following = False
        follow.updated_at = now

        await update_follow(connection, follow)
        await decrement_followers_count(connection, topic_id)

        await decrement_followed_topics_count(connection, user_id)
