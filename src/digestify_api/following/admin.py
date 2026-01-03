from uuid import UUID

from sqlmodel import select

from digestify_api.db import AsyncSession
from digestify_api.following.models import Topic, User


async def create_user(
    session: AsyncSession,
    user_id: UUID,
) -> None:
    user_result = await session.exec(
        select(User).where(User.id == user_id).with_for_update()
    )
    user = user_result.one_or_none()
    if user is not None:
        raise ValueError("User already exists")

    if user is None:
        user = User(id=user_id)
        session.add(user)


async def delete_user(
    session: AsyncSession,
    user_id: UUID,
) -> None:
    user_result = await session.exec(
        select(User).where(User.id == user_id).with_for_update()
    )
    user = user_result.one_or_none()
    if user is None:
        raise ValueError("User does not exist")

    await session.delete(user)


async def create_topic(
    session: AsyncSession,
    user_id: UUID,
    topic_id: UUID,
) -> None:
    user_result = await session.exec(
        select(User).where(User.id == user_id).with_for_update()
    )
    user = user_result.one_or_none()

    if user is None:
        raise ValueError("User does not exist")

    session.add(user)

    topic_result = await session.exec(
        select(Topic).where(Topic.id == topic_id, Topic.user_id == user_id)
    )

    topic = topic_result.one_or_none()
    if topic is not None:
        raise ValueError("Topic already exists")

    topic = Topic(id=topic_id, user_id=user_id)
    session.add(topic)


async def delete_topic(
    session: AsyncSession,
    user_id: UUID,
    topic_id: UUID,
) -> None:
    topic_result = await session.exec(
        select(Topic)
        .where(Topic.id == topic_id, Topic.user_id == user_id)
        .with_for_update()
    )
    topic = topic_result.one_or_none()
    if topic is None:
        raise ValueError("Topic does not exist")

    await session.delete(topic)
