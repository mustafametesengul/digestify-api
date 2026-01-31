from datetime import datetime, timezone
from uuid import UUID, uuid4

from digestify import Digestify
from digestify import Topic as DigestifyTopic

from digestify_api.dependencies import TaskRegistry, get_db, get_openai
from digestify_api.models import Story, StoryTaskPayload
from digestify_api.queries import (
    create_story,
    mark_task_completed,
    mark_task_failed,
    read_topic,
)

stories_task_registry = TaskRegistry()


@stories_task_registry.task
async def save_stories_by_topic(
    task_id: UUID,
    payload: StoryTaskPayload,
) -> None:
    db = get_db()
    digestify = Digestify()
    now = datetime.now(timezone.utc)

    openai = get_openai()

    async with db.get_connection() as connection:
        topic = await read_topic(connection, payload.topic_id)
        if topic is None:
            await mark_task_failed(
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
            story_create = Story(
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
            await create_story(connection, story_create)

        await mark_task_completed(connection, task_id, now)
