from datetime import UTC, date, datetime, time
from uuid import UUID

from pydantic_extra_types.timezone_name import TimeZoneName

from digestify_api.infrastructure import Command
from digestify_api.topics.infrastructure import Database, get_database


class FetchAndSaveStories(Command):
    topic_id: UUID
    schedule_version: int
    schedule_time: time
    schedule_timezone: TimeZoneName


async def fetch_and_save_stories(payload: FetchAndSaveStories) -> None:
    database = get_database()

    # async with database.transaction() as connection:
    #     now = datetime.now(UTC)

    #     topic = await _validate_and_get_topic(connection, task, payload, now)
    #     if topic is None:
    #         return None

    # digestify_topic = DigestifyTopic.model_validate(topic.model_dump())

    # digestify = Digestify()
    # openai = dependencies.openai.get_openai()

    # digest = await digestify.get_stories(digestify_topic)

    # inputs = [story.content for story in digest.stories]
    # embeddings = await openai.get_embeddings(inputs)

    # async with dependencies.db.get_db_manager().get_connection() as connection:
    #     now = datetime.now(timezone.utc)

    #     topic = await _validate_and_get_topic(connection, task, payload, now)
    #     if topic is None:
    #         return None

    #     for story, embedding in zip(digest.stories, embeddings):
    #         story_create = models.stories.Story(
    #             id=uuid4(),
    #             discarded=False,
    #             topic_id=payload.topic_id,
    #             title=story.title,
    #             image_url=None,
    #             content=story.content,
    #             language=topic.language,
    #             created_at=now,
    #             updated_at=None,
    #             embedding=embedding,
    #         )
    #         await queries.stories.create(connection, story_create)

    #     await queries.tasks.mark_as_completed(connection, task.id, now)

    #     tz = ZoneInfo(payload.schedule_timezone)

    #     next_schedule_date = payload.schedule_date + timedelta(days=1)

    #     topic.schedule_date = next_schedule_date
    #     await queries.topics.update(connection, topic)

    #     schedule = datetime.combine(
    #         next_schedule_date,
    #         topic.schedule_time,
    #         tzinfo=tz,
    #     )

    #     new_payload = FetchAndSaveStories(
    #         topic_id=payload.topic_id,
    #         schedule_version=payload.schedule_version,
    #         schedule_date=next_schedule_date,
    #         schedule_time=topic.schedule_time,
    #         schedule_timezone=payload.schedule_timezone,
    #     )

    #     task = models.tasks.Task(
    #         id=uuid4(),
    #         name="fetch_and_save_stories",
    #         payload=new_payload.model_dump_json(),
    #         created_at=now,
    #         updated_at=None,
    #         scheduled_at=schedule - timedelta(minutes=10),
    #         status=models.tasks.TaskStatus.PENDING,
    #         error_message=None,
    #     )
    #     await queries.tasks.create(connection, task)
