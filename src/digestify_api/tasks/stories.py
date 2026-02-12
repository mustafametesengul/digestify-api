from datetime import datetime, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from digestify import Digestify
from digestify import Topic as DigestifyTopic

from digestify_api import dependencies, models, queries

task_registry = dependencies.tasks.TaskRegistry()


async def _validate_and_get_topic(
    connection,
    task: models.tasks.Task,
    payload: models.stories.FetchAndSaveStoriesTask,
    now: datetime,
) -> models.topics.Topic | None:
    topic = await queries.topics.get(connection, payload.topic_id, lock=True)
    if topic is None or topic.discarded or not topic.is_active:
        await queries.tasks.mark_as_completed(connection, task.id, now)
        return None

    user = await queries.users.get(connection, topic.user_id, lock=True)
    if user is None or user.discarded:
        await queries.tasks.mark_as_completed(connection, task.id, now)
        return None

    if payload.schedule_version != topic.schedule_version:
        await queries.tasks.mark_as_completed(connection, task.id, now)
        return None

    tz = ZoneInfo(payload.schedule_timezone)
    now_in_tz = now.astimezone(tz)

    if now_in_tz.date() - topic.schedule_date > timedelta(days=1):
        topic.schedule_date = now_in_tz.date()
        await queries.topics.update(connection, topic)

    if payload.schedule_date < topic.schedule_date:
        schedule_date = topic.schedule_date
        schedule = datetime.combine(
            schedule_date,
            payload.schedule_time,
            tzinfo=tz,
        )

        new_payload = models.stories.FetchAndSaveStoriesTask(
            topic_id=payload.topic_id,
            schedule_version=payload.schedule_version,
            schedule_date=schedule_date,
            schedule_time=payload.schedule_time,
            schedule_timezone=payload.schedule_timezone,
        )

        new_task = models.tasks.Task(
            id=uuid4(),
            name="fetch_and_save_stories",
            payload=new_payload.model_dump_json(),
            created_at=now,
            updated_at=None,
            scheduled_at=schedule - timedelta(minutes=10),
            status=models.tasks.TaskStatus.PENDING,
            error_message=None,
        )

        await queries.tasks.create(connection, new_task)
        await queries.tasks.mark_as_completed(connection, task.id, now)
        return None

    return topic


@task_registry.register
async def fetch_and_save_stories(task: models.tasks.Task) -> None:
    payload = models.stories.FetchAndSaveStoriesTask.model_validate_json(task.payload)
    db = dependencies.db.get_db_manager()

    async with db.get_connection() as connection:
        now = datetime.now(timezone.utc)

        topic = await _validate_and_get_topic(connection, task, payload, now)
        if topic is None:
            return None

    digestify_topic = DigestifyTopic.model_validate(topic.model_dump())

    digestify = Digestify()
    openai = dependencies.openai.get_openai()

    digest = await digestify.get_stories(digestify_topic)

    inputs = [story.content for story in digest.stories]
    embeddings = await openai.get_embeddings(inputs)

    async with dependencies.db.get_db_manager().get_connection() as connection:
        now = datetime.now(timezone.utc)

        topic = await _validate_and_get_topic(connection, task, payload, now)
        if topic is None:
            return None

        for story, embedding in zip(digest.stories, embeddings):
            story_create = models.stories.Story(
                id=uuid4(),
                discarded=False,
                topic_id=payload.topic_id,
                title=story.title,
                image_url=None,
                content=story.content,
                language=topic.language,
                created_at=now,
                updated_at=None,
                embedding=embedding,
            )
            await queries.stories.create(connection, story_create)

        await queries.tasks.mark_as_completed(connection, task.id, now)

        tz = ZoneInfo(payload.schedule_timezone)

        next_schedule_date = payload.schedule_date + timedelta(days=1)

        topic.schedule_date = next_schedule_date
        await queries.topics.update(connection, topic)

        schedule = datetime.combine(
            next_schedule_date,
            topic.schedule_time,
            tzinfo=tz,
        )

        new_payload = models.stories.FetchAndSaveStoriesTask(
            topic_id=payload.topic_id,
            schedule_version=payload.schedule_version,
            schedule_date=next_schedule_date,
            schedule_time=topic.schedule_time,
            schedule_timezone=payload.schedule_timezone,
        )

        task = models.tasks.Task(
            id=uuid4(),
            name="fetch_and_save_stories",
            payload=new_payload.model_dump_json(),
            created_at=now,
            updated_at=None,
            scheduled_at=schedule - timedelta(minutes=10),
            status=models.tasks.TaskStatus.PENDING,
            error_message=None,
        )
        await queries.tasks.create(connection, task)
