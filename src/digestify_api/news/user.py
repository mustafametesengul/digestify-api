from datetime import UTC, datetime
from uuid import UUID

from asyncpg import Connection
from pydantic import BaseModel, Field


class User(BaseModel):
    id: UUID
    created_topics_count: int
    active_topics_count: int
    is_deleted: bool
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = None


async def create_user(conn: Connection, user: User) -> None:
    await conn.execute(
        """
        INSERT INTO users
        (id, created_topics_count, active_topics_count, is_deleted,
        created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6)
        """,
        user.id,
        user.created_topics_count,
        user.active_topics_count,
        user.is_deleted,
        user.created_at,
        user.updated_at,
    )


async def update_user(conn: Connection, user: User) -> None:
    await conn.execute(
        """
        UPDATE users
        SET created_topics_count = $2,
            active_topics_count = $3,
            is_deleted = $4,
            created_at = $5,
            updated_at = $6
        WHERE id = $1
        """,
        user.id,
        user.created_topics_count,
        user.active_topics_count,
        user.is_deleted,
        user.created_at,
        user.updated_at,
    )


async def get_user(conn: Connection, user_id: UUID, lock: bool = False) -> User | None:
    query = "SELECT * FROM users WHERE id = $1"
    if lock:
        query += " FOR UPDATE"

    row = await conn.fetchrow(query, user_id)

    if row is None:
        return None

    user = User.model_validate(dict(row))
    return user
