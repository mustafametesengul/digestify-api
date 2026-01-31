from uuid import UUID

from asyncpg import Connection

from digestify_api.models import Topic


async def topic_exists(conn: Connection, topic_id: UUID) -> bool:
    row = await conn.fetchrow(
        "SELECT 1 FROM topics WHERE id = $1",
        topic_id,
    )
    return row is not None


async def create_topic(conn: Connection, topic: Topic) -> None:
    await conn.execute(
        """
        INSERT INTO topics
        (id, user_id, discarded, name, description, language, image_url,
        is_active, followers_count, created_at, updated_at, embedding)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
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
        topic.created_at,
        topic.updated_at,
        topic.embedding,
    )


async def read_topic(
    conn: Connection, topic_id: UUID, lock: bool = False
) -> Topic | None:
    query = "SELECT * FROM topics WHERE id = $1"
    if lock:
        query += " FOR UPDATE"

    row = await conn.fetchrow(query, topic_id)

    if row is None:
        return None

    topic = Topic.model_validate(dict(row))
    return topic


async def increment_followers_count(conn: Connection, topic_id: UUID) -> None:
    await conn.execute(
        "UPDATE topics SET followers_count = followers_count + 1 WHERE id = $1",
        topic_id,
    )


async def decrement_followers_count(conn: Connection, topic_id: UUID) -> None:
    await conn.execute(
        "UPDATE topics SET followers_count = followers_count - 1 WHERE id = $1",
        topic_id,
    )


async def retrieve_topics_by_embedding(
    conn: Connection,
    embedding: str,
    limit: int = 10,
    offset: int = 0,
    threshold: float = 1.1,
) -> list[Topic]:
    rows = await conn.fetch(
        """
        SELECT *
        FROM topics
        WHERE embedding <-> $1 < $4
        ORDER BY embedding <-> $1
        LIMIT $2 OFFSET $3
        """,
        embedding,
        limit,
        offset,
        threshold,
    )
    topics = [Topic.model_validate(dict(row)) for row in rows]
    return topics
