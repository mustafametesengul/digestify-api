from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from asyncpg import Connection
from fastapi import Depends

from digestify_api.db import get_connection
from digestify_api.models import StoryCreate, StoryRead


class StoryRepository:
    def __init__(
        self,
        connection: Annotated[Connection, Depends(get_connection)],
    ) -> None:
        self._connection = connection

    async def story_exists(self, story_id: UUID) -> bool:
        row = await self._connection.fetchrow(
            "SELECT 1 FROM stories WHERE id = $1",
            story_id,
        )
        return row is not None

    async def create_story(self, story: StoryCreate) -> None:
        time = datetime.now(timezone.utc)
        await self._connection.execute(
            """
            INSERT INTO stories
            (id, discarded, created_at, updated_at, topic_id,
            title, image_url, content, language)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            story.id,
            story.discarded,
            time,
            time,
            story.topic_id,
            story.title,
            story.image_url,
            story.content,
            story.language,
        )

    async def read_story(self, story_id: UUID, lock: bool = False) -> StoryRead | None:
        query = "SELECT * FROM stories WHERE id = $1"
        if lock:
            query += " FOR UPDATE"

        row = await self._connection.fetchrow(query, story_id)

        if row is None:
            return None

        return StoryRead.model_validate(dict(row))

    async def is_story_discarded(self, story_id: UUID) -> bool:
        row = await self._connection.fetchrow(
            "SELECT discarded FROM stories WHERE id = $1",
            story_id,
        )
        if row is None:
            return False
        return row["discarded"]
