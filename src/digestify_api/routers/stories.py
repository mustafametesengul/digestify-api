from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from digestify_api.core import DBManager
from digestify_api.dependencies import get_auth, get_db
from digestify_api.models import Auth, Story
from digestify_api.queries import read_stories_by_topic

stories_router = APIRouter(
    prefix="/stories",
    tags=["stories"],
)


@stories_router.get("/")
async def get_stories(
    auth: Annotated[Auth, Depends(get_auth)],
    db: Annotated[DBManager, Depends(get_db)],
    topic_id: UUID,
) -> list[Story]:
    now: datetime = datetime.now(timezone.utc)
    async with db.get_connection() as conn:
        stories = await read_stories_by_topic(conn, topic_id, now)
    return stories
