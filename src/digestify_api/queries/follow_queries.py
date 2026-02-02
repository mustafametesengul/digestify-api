from uuid import UUID

from asyncpg import Connection

from digestify_api.models import follow_models


async def create(conn: Connection, follow: follow_models.Follow) -> None:
    await conn.execute(
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


async def update(conn: Connection, follow: follow_models.Follow) -> None:
    await conn.execute(
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


async def get(
    conn: Connection,
    user_id: UUID,
    topic_id: UUID,
    lock: bool = False,
) -> follow_models.Follow | None:
    query = "SELECT * FROM follows WHERE user_id = $1 AND topic_id = $2"
    if lock:
        query += " FOR UPDATE"

    row = await conn.fetchrow(query, user_id, topic_id)
    if row is None:
        return None
    return follow_models.Follow.model_validate(dict(row))


async def get_followed_topic_ids(
    conn: Connection,
    user_id: UUID,
) -> list[UUID]:
    rows = await conn.fetch(
        """
        SELECT topic_id
        FROM follows
        WHERE user_id = $1 AND is_following = TRUE
        """,
        user_id,
    )
    return [row["topic_id"] for row in rows]
