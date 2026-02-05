from uuid import UUID

from asyncpg import Connection

from digestify_api import models


async def create(conn: Connection, user: models.users.User) -> None:
    await conn.execute(
        """
        INSERT INTO users
        (id, username, password_hash, discarded, tier, created_topics_count,
        active_topics_count, followed_topics_count, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """,
        user.id,
        user.username,
        user.password_hash,
        user.discarded,
        user.tier,
        user.created_topics_count,
        user.active_topics_count,
        user.followed_topics_count,
        user.created_at,
        user.updated_at,
    )


async def update(conn: Connection, user: models.users.User) -> None:
    await conn.execute(
        """
        UPDATE users
        SET discarded = $2,
            tier = $3,
            created_topics_count = $4,
            followed_topics_count = $5,
            active_topics_count = $6,
            updated_at = $7
        WHERE id = $1
        """,
        user.id,
        user.discarded,
        user.tier,
        user.created_topics_count,
        user.followed_topics_count,
        user.active_topics_count,
        user.updated_at,
    )


async def get(
    conn: Connection, user_id: UUID, lock: bool = False
) -> models.users.User | None:
    query = "SELECT * FROM users WHERE id = $1"
    if lock:
        query += " FOR UPDATE"
    row = await conn.fetchrow(query, user_id)
    if row is None:
        return None
    return models.users.User.model_validate(dict(row))


async def get_by_username(conn: Connection, username: str) -> models.users.User | None:
    row = await conn.fetchrow("SELECT * FROM users WHERE username = $1", username)
    if row is None:
        return None
    return models.users.User.model_validate(dict(row))


async def increment_created_topics_count(conn: Connection, user_id: UUID) -> None:
    await conn.execute(
        """UPDATE users SET created_topics_count =
        created_topics_count + 1 WHERE id = $1""",
        user_id,
    )


async def decrement_created_topics_count(conn: Connection, user_id: UUID) -> None:
    await conn.execute(
        """UPDATE users SET created_topics_count =
        created_topics_count - 1 WHERE id = $1""",
        user_id,
    )


async def increment_active_topics_count(conn: Connection, user_id: UUID) -> None:
    await conn.execute(
        """UPDATE users SET active_topics_count =
        active_topics_count + 1 WHERE id = $1""",
        user_id,
    )


async def decrement_active_topics_count(conn: Connection, user_id: UUID) -> None:
    await conn.execute(
        """UPDATE users SET active_topics_count =
        active_topics_count - 1 WHERE id = $1""",
        user_id,
    )


async def increment_followed_topics_count(conn: Connection, user_id: UUID) -> None:
    await conn.execute(
        """UPDATE users SET followed_topics_count =
        followed_topics_count + 1 WHERE id = $1""",
        user_id,
    )


async def decrement_followed_topics_count(conn: Connection, user_id: UUID) -> None:
    await conn.execute(
        """UPDATE users SET followed_topics_count =
        followed_topics_count - 1 WHERE id = $1""",
        user_id,
    )


async def exists(conn: Connection, user_id: UUID) -> bool:
    query = "SELECT 1 FROM users WHERE id = $1"
    row = await conn.fetchrow(query, user_id)
    return row is not None


async def exists_by_username(conn: Connection, username: str) -> bool:
    row = await conn.fetchrow("SELECT 1 FROM users WHERE username = $1", username)
    return row is not None
