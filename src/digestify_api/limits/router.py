from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlmodel import select

from digestify_api.db import AsyncSession, get_session
from digestify_api.limits.exceptions import (
    FollowLimitExceeded,
    TopicLimitExceeded,
    UserAlreadyExists,
    UserNotFound,
)
from digestify_api.limits.models import User
from digestify_api.limits.schemas import SubscriptionTier, UserRead

billing_router = APIRouter(
    prefix="/billing",
    tags=["billing"],
)


async def create_user(
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: UUID,
) -> None:
    user_result = await session.exec(select(User).where(User.id == user_id))
    user = user_result.one_or_none()
    if user is not None:
        raise UserAlreadyExists()

    if user is None:
        user = User(id=user_id)
        session.add(user)


async def discard_user(
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: UUID,
) -> None:
    user_result = await session.exec(
        select(User).where(User.id == user_id).with_for_update()
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
    user_id: UUID,
) -> UserRead:
    user_result = await session.exec(select(User).where(User.id == user_id))
    user = user_result.one_or_none()
    if user is None:
        raise UserNotFound()

    return UserRead.model_validate(user.model_dump())


async def increase_created_topics_count(
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: UUID,
) -> None:
    user_result = await session.exec(
        select(User).where(User.id == user_id).with_for_update()
    )
    user = user_result.one_or_none()
    if user is None:
        raise UserNotFound()

    if (
        user.subscription_tier == SubscriptionTier.FREE
        and user.created_topics_count >= 3
    ):
        raise TopicLimitExceeded()

    user.created_topics_count += 1


async def decrease_created_topics_count(
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: UUID,
) -> None:
    user_result = await session.exec(
        select(User).where(User.id == user_id).with_for_update()
    )
    user = user_result.one_or_none()
    if user is None:
        raise UserNotFound()

    if user.created_topics_count > 0:
        user.created_topics_count -= 1


async def increase_followed_topics_count(
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: UUID,
) -> None:
    user_result = await session.exec(
        select(User).where(User.id == user_id).with_for_update()
    )
    user = user_result.one_or_none()
    if user is None:
        raise UserNotFound()

    if user.followed_topics_count >= 100:
        raise FollowLimitExceeded()

    user.followed_topics_count += 1


async def decrease_followed_topics_count(
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: UUID,
) -> None:
    user_result = await session.exec(
        select(User).where(User.id == user_id).with_for_update()
    )
    user = user_result.one_or_none()
    if user is None:
        raise UserNotFound()

    if user.followed_topics_count > 0:
        user.followed_topics_count -= 1
