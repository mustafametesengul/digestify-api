from datetime import datetime, timezone
from uuid import UUID, uuid4

from digestify import Digestify
from digestify import Topic as DigestifyTopic

from digestify_api.core import TaskRegistry
from digestify_api.dependencies import get_db
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

    async with db.get_connection() as connection:
        for story in digest.stories:
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
            )
            await create_story(connection, story_create)

        await mark_task_completed(connection, task_id, now)
