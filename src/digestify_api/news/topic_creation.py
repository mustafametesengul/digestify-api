from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import Depends, HTTPException, status
from pydantic import BaseModel, Field

from digestify_api.identity import UserClaims, require_registered_user
from digestify_api.infrastructure import enqueue_message
from digestify_api.news.dependencies import Context, get_context
from digestify_api.news.routers import api_router, message_router
from digestify_api.news.story_fetching import FetchStories
from digestify_api.news.topic import (
    Language,
    Schedule,
    Topic,
)
from digestify_api.news.topic import (
    create_topic as create_topic_in_db,
)
from digestify_api.news.user import get_user


class CreateTopicRequest(Schedule):
    name: str = Field(..., min_length=3, max_length=50)
    description: str = Field(..., min_length=0, max_length=300)
    language: Language


class CreateTopicResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    description: str
    language: Language
    image_url: str | None
    next_planned_execution: datetime


@api_router.post("/create-topic", status_code=201)
async def create_topic(
    user_claims: Annotated[UserClaims, Depends(require_registered_user)],
    context: Annotated[Context, Depends(get_context)],
    payload: CreateTopicRequest,
) -> CreateTopicResponse:
    async with context.database.transaction() as connection:
        now = datetime.now(UTC)

        user = await get_user(connection, user_claims.id, lock=True)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        if user.created_topics_count >= 50:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You have reached the maximum number of created topics (50).",
            )

        tz = ZoneInfo(payload.schedule_timezone)
        now_in_tz = now.astimezone(tz)
        if payload.schedule_time < now_in_tz.time():
            schedule_date = now_in_tz.date() + timedelta(days=1)
        else:
            schedule_date = now_in_tz.date()
        schedule = datetime.combine(schedule_date, payload.schedule_time, tzinfo=tz)

        topic = Topic(
            id=uuid4(),
            user_id=user_claims.id,
            name=payload.name,
            description=payload.description,
            language=payload.language,
            image_url=None,
            is_active=True,
            created_at=now,
            updated_at=None,
            schedule_time=payload.schedule_time,
            schedule_timezone=payload.schedule_timezone,
            schedule_version=1,
            last_execution_date=None,
            is_deleted=False,
        )

        await create_topic_in_db(connection, topic)

        scheduled_at = max(schedule - timedelta(minutes=10), now)

        command = FetchStories(
            topic_id=topic.id,
            scheduled_at=scheduled_at,
            schedule_version=topic.schedule_version,
            schedule_time=topic.schedule_time,
            schedule_timezone=topic.schedule_timezone,
            schedule_date=schedule_date,
        )
        await enqueue_message(message_router.commands, connection, command)

        response = CreateTopicResponse(
            id=topic.id,
            user_id=topic.user_id,
            name=topic.name,
            description=topic.description,
            language=topic.language,
            image_url=topic.image_url,
            next_planned_execution=schedule,
        )
        return response
