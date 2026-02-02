from datetime import datetime, timezone
from uuid import UUID, uuid4

from digestify import Digestify
from digestify import Topic as DigestifyTopic

from digestify_api.dependencies import db_manager, openai_client, task_registry
from digestify_api.models import story_models
from digestify_api.queries import story_queries, task_queries, topic_queries

story_task_registry = task_registry.TaskRegistry()


@story_task_registry.task
async def save_stories_by_topic(
    task_id: UUID,
    payload: story_models.StoryTaskPayload,
) -> None:
    db = db_manager.get_db()
    digestify = Digestify()
    now = datetime.now(timezone.utc)

    openai = openai_client.get_openai()
    async with db.get_connection() as connection:
        topic = await topic_queries.get(connection, payload.topic_id)
        if topic is None:
            await task_queries.mark_as_failed(
                connection,
                task_id,
                "Topic not found",
                now,
            )
            return

    digestify_topic = DigestifyTopic.model_validate(topic.model_dump())

    digest = await digestify.get_stories(digestify_topic)

    inputs = [story.content for story in digest.stories]
    embeddings = await openai.get_embeddings(inputs)

    async with db.get_connection() as connection:
        for story, embedding in zip(digest.stories, embeddings):
            story_create = story_models.Story(
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
            await story_queries.create(connection, story_create)

        await task_queries.mark_as_completed(connection, task_id, now)
