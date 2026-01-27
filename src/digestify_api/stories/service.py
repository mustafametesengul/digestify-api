from uuid import UUID

from digestify import Digestify, Topic

from digestify_api.db import DBService
from digestify_api.stories.models import StoryCreate, StoryRead
from digestify_api.stories.repository import StoryRepository
from digestify_api.topics import TopicNotFound, TopicRepository


class StoryService:
    def __init__(
        self,
        db: DBService,
        digestify: Digestify,
    ) -> None:
        self._db = db
        self._digestify = digestify

    async def save_stories_by_topic(self, topic_id: UUID) -> None:
        async with self._db.get_connection() as connection:
            topic_repository = TopicRepository(connection)
            topic = await topic_repository.read_topic(topic_id)
            if topic is None:
                raise TopicNotFound()

        digestify_topic = Topic.model_validate(topic.model_dump())

        digest = await self._digestify.get_stories(digestify_topic)

        stories = [
            StoryRead.model_validate(story.model_dump()) for story in digest.stories
        ]

        async with self._db.get_connection() as connection:
            story_repository = StoryRepository(connection)
            for story in stories:
                story_create = StoryCreate(
                    id=story.id,
                    discarded=False,
                    topic_id=topic_id,
                    title=story.title,
                    image_url=story.image_url,
                    content=story.content,
                    language=story.language,
                )
                await story_repository.create_story(story_create)
