from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from digestify_api.dependencies import auth_manager, db_manager
from digestify_api.exceptions import users_exceptions
from digestify_api.models import auth_models, story_models
from digestify_api.queries import follow_queries, story_queries, user_queries

router = APIRouter(
    prefix="/stories",
    tags=["stories"],
)


@router.get("/")
async def get_topic_stories(
    db: Annotated[db_manager.DBManager, Depends(db_manager.get_db)],
    topic_id: UUID,
) -> list[story_models.StoryResponse]:
    now: datetime = datetime.now(timezone.utc)
    async with db.get_connection() as conn:
        stories = await story_queries.get_by_topic_id(conn, topic_id, now)
    stories_public = [
        story_models.StoryResponse.model_validate(story) for story in stories
    ]
    return stories_public


@router.get("/")
async def get_user_stories(
    auth: Annotated[auth_models.Auth, Depends(auth_manager.get_auth)],
    db: Annotated[db_manager.DBManager, Depends(db_manager.get_db)],
) -> list[story_models.StoryResponse]:
    now: datetime = datetime.now(timezone.utc)
    async with db.get_connection() as conn:
        user = await user_queries.get(conn, auth.id)
        if user is None:
            raise users_exceptions.UserNotFound()

        topic_ids = await follow_queries.get_followed_topic_ids(conn, auth.id)
        all_stories: list[story_models.StoryResponse] = []
        for topic_id in topic_ids:
            stories = await story_queries.get_by_topic_id(conn, topic_id, now, limit=5)
            stories_public = [
                story_models.StoryResponse.model_validate(story) for story in stories
            ]
            all_stories.extend(stories_public)
    return all_stories
