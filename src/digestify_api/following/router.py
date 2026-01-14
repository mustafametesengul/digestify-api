from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlmodel import select

from digestify_api.auth import Auth, get_auth
from digestify_api.db import AsyncSession, get_session
from digestify_api.following.exceptions import (
    TopicAlreadyExists,
    TopicNotFound,
    UserAlreadyExists,
    UserNotFound,
)
from digestify_api.following.models import Follow, Topic, User

following_router = APIRouter(
    prefix="/following",
    tags=["following"],
)


async def create_user(
    session: Annotated[AsyncSession, Depends(get_session)],
    auth: Annotated[Auth, Depends(get_auth)],
) -> None:
    user_result = await session.exec(select(User).where(User.id == auth.id))
    user = user_result.one_or_none()
    if user is not None:
        raise UserAlreadyExists()

    if user is None:
        user = User(id=auth.id)
        session.add(user)


async def discard_user(
    session: Annotated[AsyncSession, Depends(get_session)],
    auth: Annotated[Auth, Depends(get_auth)],
) -> None:
    user_result = await session.exec(
        select(User).where(User.id == auth.id).with_for_update()
    )
    user = user_result.one_or_none()
    if user is None:
        raise UserNotFound()

    if user.discarded:
        return

    user.discarded = True


async def create_topic(
    session: Annotated[AsyncSession, Depends(get_session)],
    auth: Annotated[Auth, Depends(get_auth)],
    topic_id: UUID,
) -> None:
    user_result = await session.exec(
        select(User).where(User.id == auth.id).with_for_update()
    )
    user = user_result.one_or_none()
    if user is None:
        raise UserNotFound()

    topic_result = await session.exec(
        select(Topic).where(Topic.id == topic_id, Topic.user_id == auth.id)
    )
    topic = topic_result.one_or_none()
    if topic is not None:
        raise TopicAlreadyExists()

    topic = Topic(id=topic_id, user_id=auth.id, followers_count=1)
    session.add(topic)

    follow = Follow(user_id=auth.id, topic_id=topic_id, is_following=True)
    session.add(follow)

    user.followed_topics_count += 1


async def discard_topic(
    session: Annotated[AsyncSession, Depends(get_session)],
    auth: Annotated[Auth, Depends(get_auth)],
    topic_id: UUID,
) -> None:
    user_result = await session.exec(
        select(User).where(User.id == auth.id).with_for_update()
    )
    user = user_result.one_or_none()
    if user is None:
        raise UserNotFound()

    topic_result = await session.exec(
        select(Topic)
        .where(Topic.id == topic_id, Topic.user_id == auth.id)
        .with_for_update()
    )
    topic = topic_result.one_or_none()
    if topic is None:
        raise TopicNotFound()

    if topic.discarded:
        return

    user.followed_topics_count -= 1
    topic.discarded = True


@following_router.post("/follow")
async def follow(
    session: Annotated[AsyncSession, Depends(get_session)],
    auth: Annotated[Auth, Depends(get_auth)],
    topic_id: UUID,
) -> None:
    user_result = await session.exec(
        select(User).where(User.id == auth.id).with_for_update()
    )
    user = user_result.one_or_none()
    if user is None:
        raise UserNotFound()

    topic_result = await session.exec(
        select(Topic).where(Topic.id == topic_id).with_for_update()
    )
    topic = topic_result.one_or_none()
    if topic is None:
        raise TopicNotFound()

    follow_result = await session.exec(
        select(Follow)
        .where(Follow.user_id == auth.id, Follow.topic_id == topic_id)
        .with_for_update()
    )
    follow = follow_result.one_or_none()

    if follow is not None and follow.is_following:
        return

    if follow is None:
        follow = Follow(user_id=auth.id, topic_id=topic_id, is_following=True)
        session.add(follow)
    else:
        follow.is_following = True

    user.followed_topics_count += 1
    topic.followers_count += 1


@following_router.post("/unfollow")
async def unfollow(
    auth: Annotated[Auth, Depends(get_auth)],
    session: Annotated[AsyncSession, Depends(get_session)],
    topic_id: UUID,
) -> None:
    user_result = await session.exec(
        select(User).where(User.id == auth.id).with_for_update()
    )
    user = user_result.one_or_none()
    if user is None:
        raise UserNotFound()

    topic_result = await session.exec(
        select(Topic).where(Topic.id == topic_id).with_for_update()
    )
    topic = topic_result.one_or_none()
    if topic is None:
        raise TopicNotFound()

    follow_result = await session.exec(
        select(Follow)
        .where(Follow.user_id == auth.id, Follow.topic_id == topic_id)
        .with_for_update()
    )
    follow = follow_result.one_or_none()

    if follow is None or not follow.is_following:
        return

    follow.is_following = False
    user.followed_topics_count -= 1
    topic.followers_count -= 1
