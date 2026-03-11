from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import Depends
from pydantic import BaseModel

from digestify_api.identity import UserClaims, get_user_claims
from digestify_api.infrastructure import enqueue_message
from digestify_api.topics.bootstrap import Database, commands, get_database, router
from digestify_api.topics.fetch_and_save_stories import FetchAndSaveStories
from digestify_api.topics.topic import Schedule, get_topic, update_topic


class ChangeTopicSchedule(Schedule):
    topic_id: UUID


class NewSchedule(BaseModel):
    next_planned_execution: datetime


@router.post("/change_schedule", status_code=200)
async def change_schedule(
    auth: Annotated[UserClaims, Depends(get_user_claims)],
    database: Annotated[Database, Depends(get_database)],
    payload: ChangeTopicSchedule,
) -> NewSchedule:
    if auth.is_anonymous:
        raise ValueError("Authentication required")

    async with database.transaction() as connection:
        now = datetime.now(UTC)

        topic = await get_topic(connection, payload.topic_id, lock=True)
        if topic is None or topic.user_id != auth.id:
            raise ValueError("Topic not found")

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

        command = FetchAndSaveStories(
            topic_id=topic.id,
            schedule_version=topic.schedule_version,
            schedule_time=topic.schedule_time,
            schedule_timezone=topic.schedule_timezone,
            scheduled_at=scheduled_at,
            schedule_date=schedule_date,
        )
        await enqueue_message(commands, connection, command)

        new_schedule = NewSchedule(next_planned_execution=schedule)
        return new_schedule
