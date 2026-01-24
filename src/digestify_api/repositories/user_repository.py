from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from asyncpg import Connection
from fastapi import Depends

from digestify_api.db import get_connection
from digestify_api.models import UserCreate, UserRead, UserUpdate


class UserRepository:
    def __init__(
        self,
        connection: Annotated[Connection, Depends(get_connection)],
    ) -> None:
        self._connection = connection

    async def create_user(self, user: UserCreate) -> None:
        time = datetime.now(timezone.utc)
        await self._connection.execute(
            """
            INSERT INTO users
            (id, discarded, subscription_tier, created_topics_count,
            followed_topics_count, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            user.id,
            user.discarded,
            user.subscription_tier,
            user.created_topics_count,
            user.followed_topics_count,
            time,
            time,
        )

    async def update_user(self, user: UserUpdate) -> None:
        time = datetime.now(timezone.utc)
        await self._connection.execute(
            """
            UPDATE users
            SET discarded = $2,
                subscription_tier = $3,
                created_topics_count = $4,
                followed_topics_count = $5,
                updated_at = $6
            WHERE id = $1
            """,
            user.id,
            user.discarded,
            user.subscription_tier,
            user.created_topics_count,
            user.followed_topics_count,
            time,
        )

    async def read_user(self, user_id: UUID, lock: bool = False) -> UserRead | None:
        query = "SELECT * FROM users WHERE id = $1"
        if lock:
            query += " FOR UPDATE"
        row = await self._connection.fetchrow(query, user_id)
        if row is None:
            return None
        return UserRead.model_validate(dict(row))

    async def increase_created_topics_count(self, user_id: UUID) -> None:
        await self._connection.execute(
            """UPDATE users SET created_topics_count =
            created_topics_count + 1 WHERE id = $1""",
            user_id,
        )

    async def increase_followed_topics_count(self, user_id: UUID) -> None:
        await self._connection.execute(
            """UPDATE users SET followed_topics_count =
            followed_topics_count + 1 WHERE id = $1""",
            user_id,
        )

    async def user_exists(self, user_id: UUID) -> bool:
        query = "SELECT 1 FROM users WHERE id = $1"
        row = await self._connection.fetchrow(query, user_id)
        return row is not None

    async def is_user_discarded(self, user_id: UUID) -> bool:
        row = await self._connection.fetchrow(
            "SELECT discarded FROM users WHERE id = $1",
            user_id,
        )
        if row is None:
            return False
        return row["discarded"]
