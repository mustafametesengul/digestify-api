from datetime import datetime
from enum import StrEnum
from uuid import UUID

from asyncpg import Connection
from pydantic import BaseModel


class UserTier(StrEnum):
    FREE = "free"
    PREMIUM = "premium"


class User(BaseModel):
    id: UUID
    tier: UserTier
    created_at: datetime
    updated_at: datetime | None
    version: int


async def create_user(conn: Connection, user: User) -> None:
    await conn.execute(
        """
        INSERT INTO users
        (id, tier, created_at, updated_at, version)
        VALUES ($1, $2, $3, $4, $5)
        """,
        user.id,
        user.tier,
        user.created_at,
        user.updated_at,
        user.version,
    )


async def update_user(conn: Connection, user: User) -> None:
    await conn.execute(
        """
        UPDATE users
        SET tier = $2,
            created_at = $3,
            updated_at = $4,
            version = $5
        WHERE id = $1
        """,
        user.id,
        user.tier,
        user.created_at,
        user.updated_at,
        user.version,
    )


async def get_user(conn: Connection, user_id: UUID, lock: bool = False) -> User | None:
    query = "SELECT * FROM users WHERE id = $1"
    if lock:
        query += " FOR UPDATE"

    row = await conn.fetchrow(query, user_id)
    if row is None:
        return None

    return User.model_validate(dict(row))
