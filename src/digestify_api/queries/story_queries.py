from datetime import datetime
from uuid import UUID

from asyncpg import Connection
from pydantic import BaseModel


class Story(BaseModel):
    id: UUID
    discarded: bool
    topic_id: UUID
    title: str
    image_url: str | None
    content: str
    language: str
    created_at: datetime
    updated_at: datetime | None


async def story_exists(conn: Connection, story_id: UUID) -> bool:
    row = await conn.fetchrow(
        "SELECT 1 FROM stories WHERE id = $1",
        story_id,
    )
    return row is not None


async def create_story(conn: Connection, story: Story) -> None:
    await conn.execute(
        """
        INSERT INTO stories
        (id, discarded, created_at, updated_at, topic_id,
        title, image_url, content, language)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
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
    )


async def read_story(
    conn: Connection,
    story_id: UUID,
    lock: bool = False,
) -> Story | None:
    query = "SELECT * FROM stories WHERE id = $1"
    if lock:
        query += " FOR UPDATE"

    row = await conn.fetchrow(query, story_id)
    if row is None:
        return None

    return Story.model_validate(dict(row))
