from datetime import datetime
from uuid import UUID

from asyncpg import Connection
from pydantic import BaseModel

from digestify_api.membership import UserTier


class User(BaseModel):
    id: UUID
    created_topics_count: int
    active_topics_count: int
    identity_version: int
    membership_version: int
    tier: UserTier | None
    is_deleted: bool
    created_at: datetime
    updated_at: datetime | None


async def create_tables(connection: Connection) -> None:
    await connection.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY,
            created_topics_count INTEGER NOT NULL,
            active_topics_count INTEGER NOT NULL,
            identity_version INTEGER NOT NULL DEFAULT 0,
            membership_version INTEGER NOT NULL DEFAULT 0,
            tier TEXT,
            is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ
        );
        """
    )


async def create_user(conn: Connection, user: User) -> None:
    await conn.execute(
        """
        INSERT INTO users
        (id, created_topics_count, active_topics_count, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5)
        """,
        user.id,
        user.created_topics_count,
        user.active_topics_count,
        user.created_at,
        user.updated_at,
    )


async def update_user(conn: Connection, user: User) -> None:
    await conn.execute(
        """
        UPDATE users
        SET created_topics_count = $2,
            active_topics_count = $3,
            created_at = $4,
            updated_at = $5
        WHERE id = $1
        """,
        user.id,
        user.created_topics_count,
        user.active_topics_count,
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
