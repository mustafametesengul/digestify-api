from enum import StrEnum
from uuid import UUID
from typing import Literal
from digestify_api.couchdb import Document, Database


class Language(StrEnum):
    EN_US = "en-US"
    TR_TR = "tr-TR"


class Topic(Document):
    type: Literal["topic"]
    user_id: UUID
    name: str
    description: str
    language: Language
    is_deleted: bool


class TopicService:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def init(self) -> None:
        await self._database.ensure_database()
        await self._database.ensure_index(
            fields=["user_id"],
            name="topic_user_id_index",
        )

    async def create(
        self,
        topic_id: UUID,
        user_id: UUID,
        name: str,
        description: str,
        language: Language,
    ) -> None:
        topic = Topic(
            type="topic",
            id=str(topic_id),
            user_id=user_id,
            name=name,
            description=description,
            language=language,
            is_deleted=False,
        )
        await self._database.save(topic)

    async def delete(self, topic_id: UUID) -> None:
        topic = await self._database.get(Topic, str(topic_id))
        if topic is None:
            raise ValueError(f"Topic with ID {topic_id} not found.")
        topic.is_deleted = True
        await self._database.save(topic)
