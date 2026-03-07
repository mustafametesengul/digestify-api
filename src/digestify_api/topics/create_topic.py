from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import Depends
from pydantic import BaseModel, Field

from digestify_api.identity import UserClaims, get_user_claims
from digestify_api.membership import UserTier
from digestify_api.topics.fetch_and_save_stories import FetchAndSaveStories
from digestify_api.topics.infrastructure import Database, channel, get_database, router
from digestify_api.topics.topic import Language, Schedule, Topic, create_topic
from digestify_api.topics.user import get_user


class CreateTopic(Schedule):
    name: str = Field(..., min_length=3, max_length=50)
    description: str = Field(..., min_length=0, max_length=300)
    language: Language


class TopicPublic(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    description: str
    language: Language
    image_url: str | None


@router.post("/create_topic", status_code=201)
async def create_topic_(
    user_claims: Annotated[UserClaims, Depends(get_user_claims)],
    database: Annotated[Database, Depends(get_database)],
    payload: CreateTopic,
) -> None:
    if user_claims.is_anonymous:
        raise ValueError("Authentication required")

    async with database.transaction() as connection:
        now = datetime.now(UTC)

        user = await get_user(connection, user_claims.id, lock=True)
        if user is None:
            raise ValueError("User not found")

        if user.tier is UserTier.FREE:
            raise ValueError(
                "Free tier users cannot create topics. Please upgrade your subscription to create topics."
            )

        if user.created_topics_count >= 50:
            raise ValueError(
                "You have reached the maximum number of created topics (50)."
            )

        if user.active_topics_count >= 5 and user.tier is UserTier.PREMIUM:
            raise ValueError(
                "Premium tier users can have up to 5 active topics. "
                "Please deactivate some topics to create new ones."
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
            last_execution_date=schedule_date,
            is_deleted=False,
        )

        await create_topic(connection, topic)

        scheduled_at = max(schedule - timedelta(minutes=10), now)

        command = FetchAndSaveStories(
            topic_id=topic.id,
            scheduled_at=scheduled_at,
            schedule_version=topic.schedule_version,
            schedule_time=topic.schedule_time,
            schedule_timezone=topic.schedule_timezone,
        )
        await channel.save_command(connection, command)
