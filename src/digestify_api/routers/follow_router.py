from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from digestify_api.dependencies import auth_manager, db_manager
from digestify_api.exceptions import (
    follow_exceptions,
    topic_exceptions,
    users_exceptions,
)
from digestify_api.models import auth_models, follow_models
from digestify_api.queries import follow_queries, topic_queries, user_queries

router = APIRouter(
    prefix="/follows",
    tags=["follows"],
)


@router.post("/follow", status_code=200)
async def follow(
    auth: Annotated[auth_models.Auth, Depends(auth_manager.get_auth)],
    db: Annotated[db_manager.DBManager, Depends(db_manager.get_db)],
    topic_id: UUID,
) -> follow_models.Follow:
    now = datetime.now(timezone.utc)

    async with db.get_connection() as connection:
        user = await user_queries.get(connection, auth.id)
        if user is None:
            raise users_exceptions.UserNotFound()

        topic = await topic_queries.get(connection, topic_id)
        if topic is None:
            raise topic_exceptions.TopicNotFound()
        if user.followed_topics_count >= 50:
            raise follow_exceptions.FollowLimitExceeded(
                detail="User has reached the maximum number of followed topics."
            )

        follow = await follow_queries.get(connection, auth.id, topic_id, lock=True)
        if follow is None:
            follow = follow_models.Follow(
                user_id=auth.id,
                topic_id=topic_id,
                is_following=True,
                created_at=now,
                updated_at=None,
            )
            await follow_queries.create(connection, follow)
        else:
            if follow.is_following:
                raise follow_exceptions.UserAlreadyFollowsTopic()

            follow.is_following = True
            follow.updated_at = now

            await follow_queries.update(connection, follow)

        await topic_queries.increment_followers_count(connection, topic_id)
        return follow


@router.post("/unfollow", status_code=200)
async def unfollow(
    auth: Annotated[auth_models.Auth, Depends(auth_manager.get_auth)],
    db: Annotated[db_manager.DBManager, Depends(db_manager.get_db)],
    topic_id: UUID,
) -> follow_models.Follow:
    now = datetime.now(timezone.utc)
    async with db.get_connection() as connection:
        user = await user_queries.get(connection, auth.id, lock=True)
        if user is None:
            raise users_exceptions.UserNotFound()

        topic = await topic_queries.get(connection, topic_id)
        if topic is None:
            raise topic_exceptions.TopicNotFound()

        follow = await follow_queries.get(connection, auth.id, topic_id, lock=True)
        if follow is None or not follow.is_following:
            raise follow_exceptions.UserDoesNotFollowTopic()

        follow.is_following = False
        follow.updated_at = now

        await follow_queries.update(connection, follow)
        await topic_queries.decrement_followers_count(connection, topic_id)

        await user_queries.decrement_followed_topics_count(connection, auth.id)
        return follow
