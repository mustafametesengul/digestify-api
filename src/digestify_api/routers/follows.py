from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from digestify_api import dependencies, exceptions, models, queries

router = APIRouter(
    prefix="/follows",
    tags=["follows"],
)


@router.post("/follow", status_code=200)
async def follow(
    auth: Annotated[models.auth.Auth, Depends(dependencies.auth.get_auth)],
    db: Annotated[dependencies.db.DBManager, Depends(dependencies.db.get_db_manager)],
    topic_id: UUID,
) -> models.follows.Follow:
    now = datetime.now(timezone.utc)

    async with db.get_connection() as connection:
        user = await queries.users.get(connection, auth.id)
        if user is None:
            raise exceptions.users.UserNotFound()

        topic = await queries.topics.get(connection, topic_id)
        if topic is None:
            raise exceptions.topics.TopicNotFound()
        if user.followed_topics_count >= 50:
            raise exceptions.follows.FollowLimitExceeded(
                detail="User has reached the maximum number of followed topics."
            )

        follow = await queries.follows.get(connection, auth.id, topic_id, lock=True)
        if follow is None:
            follow = models.follows.Follow(
                user_id=auth.id,
                topic_id=topic_id,
                is_following=True,
                created_at=now,
                updated_at=None,
            )
            await queries.follows.create(connection, follow)
        else:
            if follow.is_following:
                raise exceptions.follows.UserAlreadyFollowsTopic()

            follow.is_following = True
            follow.updated_at = now

            await queries.follows.update(connection, follow)

        await queries.topics.increment_followers_count(connection, topic_id)
        return follow


@router.post("/unfollow", status_code=200)
async def unfollow(
    auth: Annotated[models.auth.Auth, Depends(dependencies.auth.get_auth)],
    db: Annotated[dependencies.db.DBManager, Depends(dependencies.db.get_db_manager)],
    topic_id: UUID,
) -> models.follows.Follow:
    now = datetime.now(timezone.utc)
    async with db.get_connection() as connection:
        user = await queries.users.get(connection, auth.id, lock=True)
        if user is None:
            raise exceptions.users.UserNotFound()

        topic = await queries.topics.get(connection, topic_id)
        if topic is None:
            raise exceptions.topics.TopicNotFound()
        follow = await queries.follows.get(connection, auth.id, topic_id, lock=True)
        if follow is None or not follow.is_following:
            raise exceptions.follows.UserDoesNotFollowTopic()

        follow.is_following = False
        follow.updated_at = now

        await queries.follows.update(connection, follow)
        await queries.topics.decrement_followers_count(connection, topic_id)

        await queries.users.decrement_followed_topics_count(connection, auth.id)
        return follow
