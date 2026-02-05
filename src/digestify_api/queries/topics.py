from uuid import UUID

from asyncpg import Connection

from digestify_api import models


async def exists(conn: Connection, topic_id: UUID) -> bool:
    row = await conn.fetchrow(
        "SELECT 1 FROM topics WHERE id = $1",
        topic_id,
    )
    return row is not None


async def create(conn: Connection, topic: models.topics.Topic) -> None:
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


async def update(conn: Connection, topic: models.topics.Topic) -> None:
    await conn.execute(
        """
        UPDATE topics
        SET discarded = $2,
            name = $3,
            description = $4,
            language = $5,
            image_url = $6,
            is_active = $7,
            followers_count = $8,
            created_at = $9,
            updated_at = $10,
            embedding = $11
        WHERE id = $1
        """,
        topic.id,
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


async def get(
    conn: Connection, topic_id: UUID, lock: bool = False
) -> models.topics.Topic | None:
    query = "SELECT * FROM topics WHERE id = $1"
    if lock:
        query += " FOR UPDATE"

    row = await conn.fetchrow(query, topic_id)

    if row is None:
        return None

    topic = models.topics.Topic.model_validate(dict(row))
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


async def get_by_embedding(
    conn: Connection,
    embedding: str,
    language: models.topics.Language,
    limit: int = 10,
    offset: int = 0,
    threshold: float = 1.1,
) -> list[models.topics.Topic]:
    rows = await conn.fetch(
        """
        SELECT *
        FROM topics
        WHERE embedding <-> $1 < $5 AND language = $2
        ORDER BY embedding <-> $1
        LIMIT $3 OFFSET $4
        """,
        embedding,
        language,
        limit,
        offset,
        threshold,
    )
    topics = [models.topics.Topic.model_validate(dict(row)) for row in rows]
    return topics


async def get_most_followed(
    conn: Connection,
    language: models.topics.Language,
    limit: int = 10,
    offset: int = 0,
) -> list[models.topics.Topic]:
    rows = await conn.fetch(
        """
        SELECT *
        FROM topics
        WHERE language = $3
        ORDER BY followers_count DESC
        LIMIT $1 OFFSET $2
        """,
        limit,
        offset,
        language,
    )
    topics = [models.topics.Topic.model_validate(dict(row)) for row in rows]
    return topics
