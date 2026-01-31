from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from digestify_api.dependencies import DBManager, get_auth, get_db
from digestify_api.exceptions import (
    FollowLimitExceeded,
    TopicNotFound,
    UserAlreadyFollowsTopic,
    UserDoesNotFollowTopic,
    UserNotFound,
)
from digestify_api.models import Auth, Follow
from digestify_api.queries import (
    create_follow,
    decrement_followed_topics_count,
    decrement_followers_count,
    increment_followers_count,
    read_follow,
    read_topic,
    read_user,
    update_follow,
)

follows_router = APIRouter(
    prefix="/follows",
    tags=["follows"],
)


@follows_router.post("/follow", status_code=200)
async def follow(
    auth: Annotated[Auth, Depends(get_auth)],
    db: Annotated[DBManager, Depends(get_db)],
    topic_id: UUID,
) -> Follow:
    now = datetime.now(timezone.utc)

    async with db.get_connection() as connection:
        user = await read_user(connection, auth.id)
        if user is None:
            raise UserNotFound()

        topic = await read_topic(connection, topic_id)
        if topic is None:
            raise TopicNotFound()

        if user.followed_topics_count >= 50:
            raise FollowLimitExceeded(
                detail="User has reached the maximum number of followed topics."
            )

        follow = await read_follow(connection, auth.id, topic_id, lock=True)

        if follow is None:
            follow = Follow(
                user_id=auth.id,
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
        return follow


@follows_router.post("/unfollow", status_code=200)
async def unfollow(
    auth: Annotated[Auth, Depends(get_auth)],
    db: Annotated[DBManager, Depends(get_db)],
    topic_id: UUID,
) -> Follow:
    now = datetime.now(timezone.utc)
    async with db.get_connection() as connection:
        user = await read_user(connection, auth.id, lock=True)
        if user is None:
            raise UserNotFound()

        topic = await read_topic(connection, topic_id)
        if topic is None:
            raise TopicNotFound()

        follow = await read_follow(connection, auth.id, topic_id, lock=True)
        if follow is None or not follow.is_following:
            raise UserDoesNotFollowTopic()

        follow.is_following = False
        follow.updated_at = now

        await update_follow(connection, follow)
        await decrement_followers_count(connection, topic_id)

        await decrement_followed_topics_count(connection, auth.id)
        return follow
