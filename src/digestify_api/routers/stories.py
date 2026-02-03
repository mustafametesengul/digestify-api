from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from digestify_api import dependencies, exceptions, models, queries

router = APIRouter(
    prefix="/stories",
    tags=["stories"],
)


@router.get("/get_topic_stories")
async def get_topic_stories(
    db: Annotated[dependencies.db.DBManager, Depends(dependencies.db.get_db_manager)],
    topic_id: UUID,
) -> list[models.stories.StoryResponse]:
    now: datetime = datetime.now(timezone.utc)
    async with db.get_connection() as conn:
        stories = await queries.stories.get_by_topic_id(conn, topic_id, now)
    stories_public = [
        models.stories.StoryResponse.model_validate(story) for story in stories
    ]
    return stories_public


@router.get("/get_user_stories")
async def get_user_stories(
    auth: Annotated[models.auth.Auth, Depends(dependencies.auth.get_auth)],
    db: Annotated[dependencies.db.DBManager, Depends(dependencies.db.get_db_manager)],
) -> list[models.stories.StoryResponse]:
    now: datetime = datetime.now(timezone.utc)
    async with db.get_connection() as conn:
        user = await queries.users.get(conn, auth.id)
        if user is None:
            raise exceptions.users.UserNotFound()

        topic_ids = await queries.follows.get_followed_topic_ids(conn, auth.id)
        all_stories: list[models.stories.StoryResponse] = []
        for topic_id in topic_ids:
            stories = await queries.stories.get_by_topic_id(
                conn, topic_id, now, limit=5
            )
            stories_public = [
                models.stories.StoryResponse.model_validate(story) for story in stories
            ]
            all_stories.extend(stories_public)
    return all_stories
