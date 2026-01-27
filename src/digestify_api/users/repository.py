from uuid import UUID

from asyncpg import Connection

from digestify_api.users.models import User


class UserRepository:
    def __init__(
        self,
        connection: Connection,
    ) -> None:
        self._connection = connection

    async def create_user(self, user: User) -> None:
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
            user.created_at,
            user.updated_at,
        )

    async def update_user(self, user: User) -> None:
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
            user.updated_at,
        )

    async def read_user(self, user_id: UUID, lock: bool = False) -> User | None:
        query = "SELECT * FROM users WHERE id = $1"
        if lock:
            query += " FOR UPDATE"
        row = await self._connection.fetchrow(query, user_id)
        if row is None:
            return None
        return User.model_validate(dict(row))

    async def increment_created_topics_count(self, user_id: UUID) -> None:
        await self._connection.execute(
            """UPDATE users SET created_topics_count =
            created_topics_count + 1 WHERE id = $1""",
            user_id,
        )

    async def decrement_created_topics_count(self, user_id: UUID) -> None:
        await self._connection.execute(
            """UPDATE users SET created_topics_count =
            created_topics_count - 1 WHERE id = $1""",
            user_id,
        )

    async def increment_followed_topics_count(self, user_id: UUID) -> None:
        await self._connection.execute(
            """UPDATE users SET followed_topics_count =
            followed_topics_count + 1 WHERE id = $1""",
            user_id,
        )

    async def decrement_followed_topics_count(self, user_id: UUID) -> None:
        await self._connection.execute(
            """UPDATE users SET followed_topics_count =
            followed_topics_count - 1 WHERE id = $1""",
            user_id,
        )

    async def user_exists(self, user_id: UUID) -> bool:
        query = "SELECT 1 FROM users WHERE id = $1"
        row = await self._connection.fetchrow(query, user_id)
        return row is not None
