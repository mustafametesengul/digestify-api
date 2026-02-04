from datetime import datetime, timezone
from uuid import UUID, uuid4

from digestify import Digestify
from digestify import Topic as DigestifyTopic

from digestify_api import dependencies, models, queries

task_registry = dependencies.tasks.TaskRegistry()


@task_registry.register
async def fetch_and_save_stories(
    task_id: UUID,
    payload: models.stories.StoryTaskPayload,
) -> None:
    db = dependencies.db.get_db_manager()
    digestify = Digestify()
    now = datetime.now(timezone.utc)

    openai = dependencies.openai.get_openai()
    async with db.get_connection() as connection:
        topic = await queries.topics.get(connection, payload.topic_id)
        if topic is None or not topic.is_active:
            await queries.tasks.mark_as_completed(connection, task_id, now)
            return

    digestify_topic = DigestifyTopic.model_validate(topic.model_dump())

    digest = await digestify.get_stories(digestify_topic)

    inputs = [story.content for story in digest.stories]
    embeddings = await openai.get_embeddings(inputs)

    async with dependencies.db.get_db_manager().get_connection() as connection:
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

        topic = await queries.topics.get(
            connection,
            payload.topic_id,
            lock=True,
        )
        if topic is None:
            raise ValueError("Topic not found when scheduling next fetch")

        if topic.is_active:
            task = models.tasks.Task(
                id=uuid4(),
                name="fetch_and_save_stories",
                payload=payload.model_dump_json(),
                created_at=now,
                updated_at=None,
                scheduled_at=now,
                status=models.tasks.TaskStatus.PENDING,
                error_message=None,
            )
            await queries.tasks.create(connection, task)
