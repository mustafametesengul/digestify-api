from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlmodel import select

from digestify_api.auth import Auth, get_auth
from digestify_api.billing.exceptions import (
    TopicAlreadyExists,
    TopicLimitExceeded,
    TopicNotFound,
    UserAlreadyExists,
    UserNotFound,
)
from digestify_api.billing.models import Topic, User
from digestify_api.billing.schemas import SubscriptionTier, UserRead
from digestify_api.db import AsyncSession, get_session

billing_router = APIRouter(
    prefix="/billing",
    tags=["billing"],
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


@billing_router.get("/user")
async def get_user(
    session: Annotated[AsyncSession, Depends(get_session)],
    auth: Annotated[Auth, Depends(get_auth)],
) -> UserRead:
    user_result = await session.exec(select(User).where(User.id == auth.id))
    user = user_result.one_or_none()
    if user is None:
        raise UserNotFound()

    return UserRead.model_validate(user.model_dump())


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

    if (
        user.created_topics_count >= 1
        and user.subscription_tier is SubscriptionTier.FREE
    ):
        raise TopicLimitExceeded("Free tier users can only create up to 1 topic")

    if (
        user.created_topics_count >= 5
        and user.subscription_tier is SubscriptionTier.PREMIUM
    ):
        raise TopicLimitExceeded("Premium tier users can only create up to 5 topics")

    user.created_topics_count += 1

    topic = Topic(id=topic_id, user_id=auth.id)
    session.add(topic)


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

    topic.discarded = True
    user.created_topics_count -= 1
