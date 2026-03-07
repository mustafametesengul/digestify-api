from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends

from digestify_api.identity import UserClaims, get_user_claims
from digestify_api.topics.infrastructure import Database, get_database
from digestify_api.topics.router import router
from digestify_api.topics.topic import Schedule


class ChangeTopicSchedule(Schedule):
    topic_id: UUID


@router.post("/change_schedule", status_code=200)
async def change_schedule(
    auth: Annotated[UserClaims, Depends(get_user_claims)],
    database: Annotated[Database, Depends(get_database)],
    payload: ChangeTopicSchedule,
) -> None:
    if auth.is_anonymous:
        raise ValueError("Authentication required")

    async with database.transaction() as connection:
        now = datetime.now(UTC)

        topic = await queries.topics.get(connection, payload.topic_id, lock=True)
        if topic is None or topic.user_id != auth.id:
            raise exceptions.topics.TopicNotFound()

        tz = ZoneInfo(payload.schedule_timezone)
        now_in_tz = now.astimezone(tz)
        if payload.schedule_time < now_in_tz.time():
            schedule_date = now_in_tz.date() + timedelta(days=1)
        else:
            schedule_date = now_in_tz.date()
        schedule_date = max(schedule_date, topic.schedule_date)
        schedule = datetime.combine(schedule_date, payload.schedule_time, tzinfo=tz)

        topic.schedule_time = payload.schedule_time
        topic.schedule_timezone = payload.schedule_timezone
        topic.schedule_version += 1
        topic.updated_at = now
        topic.schedule_date = schedule_date

        await queries.topics.update(connection, topic)

        task_payload = schemas.stories.FetchAndSaveStoriesTask(
            topic_id=topic.id,
            schedule_version=topic.schedule_version,
            schedule_date=topic.schedule_date,
            schedule_time=topic.schedule_time,
            schedule_timezone=topic.schedule_timezone,
        )

        task = schemas.tasks.Task(
            id=uuid4(),
            name="fetch_and_save_stories",
            status=schemas.tasks.TaskStatus.PENDING,
            created_at=now,
            updated_at=None,
            payload=task_payload.model_dump_json(),
            scheduled_at=_get_scheduled_at(schedule, now),
            error_message=None,
        )
        await queries.tasks.create(connection, task)
