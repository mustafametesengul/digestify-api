from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import Depends, HTTPException, status
from pydantic import BaseModel

from digestify_api.identity import UserClaims
from digestify_api.infrastructure import enqueue_message
from digestify_api.news.dependencies import Context, get_context, get_user_claims
from digestify_api.news.routers import api_router, message_router
from digestify_api.news.story_fetching import FetchStories
from digestify_api.news.topic import Schedule, get_topic, update_topic


class ChangeScheduleRequest(Schedule):
    topic_id: UUID


class ChangeScheduleResponse(BaseModel):
    next_planned_execution: datetime


@api_router.post("/change-schedule", status_code=200)
async def change_schedule(
    user_claims: Annotated[UserClaims, Depends(get_user_claims)],
    context: Annotated[Context, Depends(get_context)],
    payload: ChangeScheduleRequest,
) -> ChangeScheduleResponse:
    async with context.database.transaction() as connection:
        now = datetime.now(UTC)

        topic = await get_topic(connection, payload.topic_id, lock=True)
        if topic is None or topic.user_id != user_claims.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found"
            )

        tz = ZoneInfo(payload.schedule_timezone)
        now_in_tz = now.astimezone(tz)

        if payload.schedule_time < now_in_tz.time():
            schedule_date = now_in_tz.date() + timedelta(days=1)
        else:
            schedule_date = now_in_tz.date()

        if (
            topic.last_execution_date is not None
            and schedule_date <= topic.last_execution_date
        ):
            schedule_date = topic.last_execution_date + timedelta(days=1)

        schedule = datetime.combine(schedule_date, payload.schedule_time, tzinfo=tz)

        topic.schedule_time = payload.schedule_time
        topic.schedule_timezone = payload.schedule_timezone
        topic.schedule_version += 1
        topic.updated_at = now

        await update_topic(connection, topic)

        scheduled_at = max(schedule - timedelta(minutes=10), now)

        command = FetchStories(
            topic_id=topic.id,
            schedule_version=topic.schedule_version,
            schedule_time=topic.schedule_time,
            schedule_timezone=topic.schedule_timezone,
            scheduled_at=scheduled_at,
            schedule_date=schedule_date,
        )
        await enqueue_message(message_router.events, connection, command)

        response = ChangeScheduleResponse(next_planned_execution=schedule)
        return response
