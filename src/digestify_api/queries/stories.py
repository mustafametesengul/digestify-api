from datetime import datetime
from uuid import UUID

from asyncpg import Connection

from digestify_api import models


async def exists(conn: Connection, story_id: UUID) -> bool:
    row = await conn.fetchrow(
        "SELECT 1 FROM stories WHERE id = $1",
        story_id,
    )
    return row is not None


async def create(conn: Connection, story: models.stories.Story) -> None:
    await conn.execute(
        """
        INSERT INTO stories
        (id, discarded, created_at, updated_at, topic_id,
        title, image_url, content, language, embedding)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """,
        story.id,
        story.discarded,
        story.created_at,
        story.updated_at,
        story.topic_id,
        story.title,
        story.image_url,
        story.content,
        story.language,
        story.embedding,
    )


async def get(
    conn: Connection,
    story_id: UUID,
    lock: bool = False,
) -> models.stories.Story | None:
    query = "SELECT * FROM stories WHERE id = $1"
    if lock:
        query += " FOR UPDATE"

    row = await conn.fetchrow(query, story_id)
    if row is None:
        return None

    return models.stories.Story.model_validate(dict(row))


async def get_by_topic_id(
    conn: Connection,
    topic_id: UUID,
    time: datetime,
    limit: int = 20,
) -> list[models.stories.Story]:
    rows = await conn.fetch(
        """
        SELECT * FROM stories
        WHERE topic_id = $1 AND created_at <= $2
        ORDER BY created_at DESC
        LIMIT $3
        """,
        topic_id,
        time,
        limit,
    )
    return [models.stories.Story.model_validate(dict(row)) for row in rows]


async def get_latest_story_creation_time(
    conn: Connection,
    topic_id: UUID,
) -> datetime | None:
    row = await conn.fetchrow(
        """
        SELECT created_at FROM stories
        WHERE topic_id = $1
        ORDER BY created_at DESC
        LIMIT 1
        """,
        topic_id,
    )
    if row is None:
        return None

    return row["created_at"]
