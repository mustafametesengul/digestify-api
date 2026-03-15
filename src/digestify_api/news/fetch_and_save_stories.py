from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import asyncpg
from digestify import Digestify
from digestify import Topic as DigestifyTopic
from pydantic_extra_types.timezone_name import TimeZoneName

from digestify_api.infrastructure import (
    Command,
    HandledMessage,
    create_handled_message,
    enqueue_message,
)
from digestify_api.news.dependencies import Context, message_router
from digestify_api.news.story import Story, create_story
from digestify_api.news.topic import Topic, get_topic, update_topic


class FetchAndSaveStories(Command):
    topic_id: UUID
    schedule_version: int
    schedule_time: time
    schedule_timezone: TimeZoneName
    schedule_date: date


async def _validate_and_fetch_topic(
    connection: asyncpg.Connection,
    payload: FetchAndSaveStories,
    handled_message: HandledMessage,
    now: datetime,
) -> Topic | None:
    tz = ZoneInfo(payload.schedule_timezone)

    topic = await get_topic(connection, payload.topic_id, lock=True)

    if (
        topic is None
        or topic.schedule_version != payload.schedule_version
        or topic.is_deleted
        or not topic.is_active
    ):
        await create_handled_message(connection, handled_message)
        return

    next_schedule_date: date | None = None

    planned_at = datetime.combine(
        payload.schedule_date,
        topic.schedule_time,
        tzinfo=tz,
    )
    if now > planned_at + timedelta(hours=2):
        next_schedule_date = now.astimezone(tz).date() + timedelta(days=1)

    if (
        topic.last_execution_date is not None
        and payload.schedule_date <= topic.last_execution_date
    ):
        next_schedule_date = topic.last_execution_date + timedelta(days=1)

    if next_schedule_date is not None:
        schedule = datetime.combine(
            next_schedule_date,
            topic.schedule_time,
            tzinfo=tz,
        )
        scheduled_at = max(schedule - timedelta(minutes=10), now)

        new_command = FetchAndSaveStories(
            topic_id=payload.topic_id,
            schedule_version=payload.schedule_version,
            schedule_time=topic.schedule_time,
            schedule_timezone=payload.schedule_timezone,
            schedule_date=next_schedule_date,
            scheduled_at=scheduled_at,
        )
        await enqueue_message(message_router.commands, connection, new_command)

        await create_handled_message(connection, handled_message)
        return


@message_router.receive(channel=message_router.commands)
async def fetch_and_save_stories(
    context: Context,
    payload: FetchAndSaveStories,
) -> None:
    database = context.database

    handled_message = HandledMessage(
        message_id=payload.id,
        handler_name="fetch_and_save_stories",
    )

    async with database.transaction() as connection:
        now = datetime.now(UTC)
        topic = await _validate_and_fetch_topic(
            connection,
            payload,
            handled_message,
            now,
        )
        if topic is None:
            return

    digestify_topic = DigestifyTopic.model_validate(topic.model_dump())

    digestify = Digestify()

    digest = await digestify.get_stories(digestify_topic)

    async with database.transaction() as connection:
        now = datetime.now(UTC)
        topic = await _validate_and_fetch_topic(
            connection,
            payload,
            handled_message,
            now,
        )
        if topic is None:
            return

        for story in digest.stories:
            story = Story(
                id=uuid4(),
                topic_id=topic.id,
                title=story.title,
                image_url=None,
                content=story.content,
                language=topic.language,
                created_at=now,
                updated_at=None,
                is_deleted=False,
            )
            await create_story(connection, story)

        topic.last_execution_date = payload.schedule_date
        topic.updated_at = now
        await update_topic(connection, topic)

        await create_handled_message(connection, handled_message)

        tz = ZoneInfo(payload.schedule_timezone)
        next_schedule_date = payload.schedule_date + timedelta(days=1)
        schedule = datetime.combine(
            next_schedule_date,
            topic.schedule_time,
            tzinfo=tz,
        )
        scheduled_at = max(schedule - timedelta(minutes=10), now)

        new_command = FetchAndSaveStories(
            topic_id=payload.topic_id,
            schedule_version=payload.schedule_version,
            schedule_time=topic.schedule_time,
            schedule_timezone=payload.schedule_timezone,
            schedule_date=next_schedule_date,
            scheduled_at=scheduled_at,
        )
        await enqueue_message(message_router.commands, connection, new_command)
