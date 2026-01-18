from typing import Annotated
from uuid import UUID

from asyncpg import Connection
from fastapi import Depends

from digestify_api.db import get_connection
from digestify_api.models import TopicCreate


class TopicRepository:
    def __init__(
        self,
        connection: Annotated[Connection, Depends(get_connection)],
    ) -> None:
        self._connection = connection

    async def topic_exists(self, topic_id: UUID) -> bool:
        row = await self._connection.fetchrow(
            "SELECT 1 FROM topics WHERE id = $1",
            topic_id,
        )
        return row is not None

    async def create_topic(self, topic: TopicCreate) -> None:
        await self._connection.execute(
            "INSERT INTO topics (id, user_id, discarded, name, description, language, image_url, is_active, followers_count) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)",
            topic.id,
            topic.user_id,
            topic.discarded,
            topic.name,
            topic.description,
            topic.language,
            topic.image_url,
            topic.is_active,
            topic.followers_count,
        )

    async def read_topic(
        self, topic_id: UUID, lock: bool = False
    ) -> TopicCreate | None:
        query = "SELECT * FROM topics WHERE id = $1"
        if lock:
            query += " FOR UPDATE"

        row = await self._connection.fetchrow(query, topic_id)

        if row is None:
            return None

        topic = TopicCreate.model_validate(row, from_attributes=True)
        return topic

    async def is_topic_discarded(self, topic_id: UUID) -> bool:
        row = await self._connection.fetchrow(
            "SELECT discarded FROM topics WHERE id = $1",
            topic_id,
        )
        if row is None:
            return False
        return row["discarded"]

    async def increase_followers_count(self, topic_id: UUID) -> None:
        await self._connection.execute(
            "UPDATE topics SET followers_count = followers_count + 1 WHERE id = $1",
            topic_id,
        )

    async def decrease_followers_count(self, topic_id: UUID) -> None:
        await self._connection.execute(
            "UPDATE topics SET followers_count = followers_count - 1 WHERE id = $1",
            topic_id,
        )
