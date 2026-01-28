from uuid import UUID

from asyncpg import Connection

from digestify_api.follow_repository.models import Follow


class FollowRepository:
    def __init__(
        self,
        connection: Connection,
    ) -> None:
        self._connection = connection

    async def create_follow(self, follow: Follow) -> None:
        await self._connection.execute(
            """
            INSERT INTO follows
            (user_id, topic_id, is_following, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5)
            """,
            follow.user_id,
            follow.topic_id,
            follow.is_following,
            follow.created_at,
            follow.updated_at,
        )

    async def update_follow(self, follow: Follow) -> None:
        await self._connection.execute(
            """
            UPDATE follows
            SET is_following = $3, updated_at = $4
            WHERE user_id = $1 AND topic_id = $2
            """,
            follow.user_id,
            follow.topic_id,
            follow.is_following,
            follow.updated_at,
        )

    async def read_follow(
        self,
        user_id: UUID,
        topic_id: UUID,
        lock: bool = False,
    ) -> Follow | None:
        query = "SELECT * FROM follows WHERE user_id = $1 AND topic_id = $2"
        if lock:
            query += " FOR UPDATE"

        row = await self._connection.fetchrow(query, user_id, topic_id)
        if row is None:
            return None
        return Follow.model_validate(dict(row))
