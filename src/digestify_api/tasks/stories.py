from datetime import datetime, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from digestify import Digestify
from digestify import Topic as DigestifyTopic

from digestify_api import dependencies, models, queries

task_registry = dependencies.tasks.TaskRegistry()


@task_registry.register
async def fetch_and_save_stories(task: models.tasks.Task) -> None:
    task_id = task.id
    payload = models.stories.FetchAndSaveStoriesTask.model_validate_json(task.payload)
    db = dependencies.db.get_db_manager()
    digestify = Digestify()
    openai = dependencies.openai.get_openai()

    async with db.get_connection() as connection:
        now = datetime.now(timezone.utc)

        topic = await queries.topics.get(connection, payload.topic_id, lock=True)
        if topic is None:
            await queries.tasks.mark_as_completed(connection, task_id, now)
            return

        user = await queries.users.get(connection, topic.user_id)
        if user is None:
            await queries.tasks.mark_as_completed(connection, task_id, now)
            return

        tz = ZoneInfo(payload.schedule_timezone)
        now_in_tz = now.astimezone(tz)

        if (
            user.tier_last_confirmed_at is None
            or now - user.tier_last_confirmed_at > timedelta(days=30)
            or not topic.is_active
            or topic.discarded
            or user.discarded
            or payload.schedule_date == now_in_tz.date()
            or payload.schedule_version != topic.schedule_version
        ):
            await queries.tasks.mark_as_completed(connection, task_id, now)
            return

        topic.schedule_date = now_in_tz.date() + timedelta(days=1)
        await queries.topics.update(connection, topic)

    digestify_topic = DigestifyTopic.model_validate(topic.model_dump())

    digest = await digestify.get_stories(digestify_topic)

    inputs = [story.content for story in digest.stories]
    embeddings = await openai.get_embeddings(inputs)

    async with dependencies.db.get_db_manager().get_connection() as connection:
        topic = await queries.topics.get(
            connection,
            payload.topic_id,
            lock=True,
        )

        if topic is None or topic.discarded or not topic.is_active:
            await queries.tasks.mark_as_completed(connection, task_id, now)
            return

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

        await queries.tasks.mark_as_completed(connection, task_id, now)

        tz = ZoneInfo(topic.schedule_timezone)
        now_in_tz = datetime.now(tz)
        if topic.schedule_time < now_in_tz.time():
            schedule_date = now_in_tz.date() + timedelta(days=1)
        else:
            schedule_date = now_in_tz.date()
        schedule = datetime.combine(schedule_date, topic.schedule_time, tzinfo=tz)

        new_payload = models.stories.FetchAndSaveStoriesTask(
            topic_id=payload.topic_id,
            schedule_version=payload.schedule_version,
            schedule_date=schedule_date,
            schedule_time=topic.schedule_time,
            schedule_timezone=payload.schedule_timezone,
        )

        task = models.tasks.Task(
            id=uuid4(),
            name="fetch_and_save_stories",
            payload=new_payload.model_dump_json(),
            created_at=now,
            updated_at=None,
            scheduled_at=schedule,
            status=models.tasks.TaskStatus.PENDING,
            error_message=None,
        )
        await queries.tasks.create(connection, task)
