from datetime import datetime, timezone
from uuid import UUID

from asyncpg import Connection

from digestify_api.topics.models import (
    FollowCreate,
    FollowRead,
    FollowUpdate,
    TopicCreate,
)


class TopicRepository:
    def __init__(
        self,
        connection: Connection,
    ) -> None:
        self._connection = connection

    async def topic_exists(self, topic_id: UUID) -> bool:
        row = await self._connection.fetchrow(
            "SELECT 1 FROM topics WHERE id = $1",
            topic_id,
        )
        return row is not None

    async def create_topic(self, topic: TopicCreate) -> None:
        time = datetime.now(timezone.utc)
        await self._connection.execute(
            """
            INSERT INTO topics
            (id, user_id, discarded, name, description, language, image_url,
            is_active, followers_count, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            """,
            topic.id,
            topic.user_id,
            topic.discarded,
            topic.name,
            topic.description,
            topic.language,
            topic.image_url,
            topic.is_active,
            topic.followers_count,
            time,
            time,
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

        topic = TopicCreate.model_validate(dict(row))
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

    async def create_follow(self, follow: FollowCreate) -> None:
        time = datetime.now(timezone.utc)
        await self._connection.execute(
            """
            INSERT INTO follows
            (user_id, topic_id, is_following, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5)
            """,
            follow.user_id,
            follow.topic_id,
            follow.is_following,
            time,
            time,
        )

    async def update_follow(self, follow: FollowUpdate) -> None:
        time = datetime.now(timezone.utc)
        await self._connection.execute(
            """
            UPDATE follows
            SET is_following = $3, updated_at = $4
            WHERE user_id = $1 AND topic_id = $2
            """,
            follow.user_id,
            follow.topic_id,
            follow.is_following,
            time,
        )

    async def read_follow(
        self, user_id: UUID, topic_id: UUID, lock: bool = False
    ) -> FollowRead | None:
        query = "SELECT * FROM follows WHERE user_id = $1 AND topic_id = $2"
        if lock:
            query += " FOR UPDATE"

        row = await self._connection.fetchrow(query, user_id, topic_id)
        if row is None:
            return None
        return FollowRead.model_validate(dict(row))
