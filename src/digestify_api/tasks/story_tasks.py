from datetime import datetime, timezone
from uuid import UUID, uuid4

from digestify import Digestify
from digestify import Topic as DigestifyTopic
from pydantic import BaseModel

from digestify_api.db import get_db
from digestify_api.exceptions.topic_exceptions import TopicNotFound
from digestify_api.queries.story_queries import Story, create_story
from digestify_api.queries.topic_queries import read_topic
from digestify_api.task_processor import TaskRegistry


class StoryTaskPayload(BaseModel):
    topic_id: UUID


story_task_registry = TaskRegistry()


@story_task_registry.task
async def save_stories_by_topic(
    payload: StoryTaskPayload,
) -> None:
    db = get_db()
    digestify = Digestify()
    now = datetime.now(timezone.utc)
    async with db.get_connection() as connection:
        topic = await read_topic(connection, payload.topic_id)
        if topic is None:
            raise TopicNotFound()

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
