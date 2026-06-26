from datetime import datetime, UTC
from digestify_api.topic import Language
from uuid import UUID
from typing import Literal
from digestify_api.couchdb import Document


class Story(Document):
    type: Literal["story"] = "story"
    topic_id: UUID
    title: str
    body: str
    language: Language
    created_at: datetime


class StoryService:
    def __init__(self, database) -> None:
        self._database = database

    async def init(self) -> None:
        await self._database.ensure_database()
        await self._database.ensure_index(
            fields=["topic_id"],
            name="story_topic_id_index",
        )

    async def create(
        self,
        story_id: UUID,
        topic_id: UUID,
        title: str,
        body: str,
    ) -> None:
        story = Story(
            type="story",
            id=str(story_id),
            topic_id=topic_id,
            title=title,
            body=body,
            language=Language.EN_US,
            created_at=datetime.now(UTC),
        )
        await self._database.save(story)
