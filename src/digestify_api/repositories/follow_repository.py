from typing import Annotated
from uuid import UUID

from asyncpg import Connection
from fastapi import Depends

from digestify_api.db import get_connection
from digestify_api.models import FollowCreate, FollowRead, FollowUpdate


class FollowRepository:
    def __init__(
        self,
        connection: Annotated[Connection, Depends(get_connection)],
    ) -> None:
        self._connection = connection

    async def create_follow(self, follow: FollowCreate) -> None:
        await self._connection.execute(
            "INSERT INTO follows (user_id, topic_id, is_following) VALUES ($1, $2, $3)",
            follow.user_id,
            follow.topic_id,
            follow.is_following,
        )

    async def update_follow(self, follow: FollowUpdate) -> None:
        await self._connection.execute(
            "UPDATE follows SET is_following = $3 WHERE user_id = $1 AND topic_id = $2",
            follow.user_id,
            follow.topic_id,
            follow.is_following,
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
        return FollowRead.model_validate(row, from_attributes=True)
