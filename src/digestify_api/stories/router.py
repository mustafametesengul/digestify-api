from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlmodel import select

from digestify_api.auth import Auth, get_auth
from digestify_api.db import AsyncSession, get_session
from digestify_api.stories.exceptions import TopicNotFound
from digestify_api.stories.models import Story, Topic


async def research_stories(
    session: Annotated[AsyncSession, Depends(get_session)],
    topic_id: UUID,
):
    topic_result = await session.exec(select(Topic).where(Topic.id == topic_id))
    topic = topic_result.one_or_none()
    if topic is None:
        raise TopicNotFound()

    # Placeholder for research logic
    for _ in range(3):  # Example: create 3 dummy stories
        story = Story(
            topic_id=topic.id,
            title="Sample Title",
            image_url="http://example.com/image.jpg",
            content="Sample Content",
            language="en",
        )
        session.add(story)

    await session.commit()


async def update_topic(
    session: Annotated[AsyncSession, Depends(get_session)],
    topic_id: UUID,
    name: str | None = None,
    description: str | None = None,
    language: str | None = None,
):
    topic_result = await session.exec(
        select(Topic).where(Topic.id == topic_id).with_for_update()
    )
    topic = topic_result.one_or_none()
    if topic is None:
        raise TopicNotFound()

    if name is not None:
        topic.name = name
    if description is not None:
        topic.description = description
    if language is not None:
        topic.language = language
