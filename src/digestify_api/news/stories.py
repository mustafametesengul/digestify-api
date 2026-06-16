from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from pydantic import BaseModel

from digestify_api.infrastructure.token_generation import UserClaims
from digestify_api.news.dependencies import (
    Context,
    get_context,
    require_authenticated_user,
)
from digestify_api.news.routers import api_router
from digestify_api.news.story import Story
from digestify_api.news.topic import Language

DEFAULT_STORY_LIMIT = 20
MAX_STORY_LIMIT = 100


class StoryResponse(BaseModel):
    id: UUID
    title: str
    body: str
    language: Language
    created_at: datetime

    @classmethod
    def of(cls, story: Story) -> "StoryResponse":
        return cls(
            id=UUID(story.id),
            title=story.title,
            body=story.body,
            language=story.language,
            created_at=story.created_at,
        )


@api_router.get("/latest-stories")
async def latest_stories(
    context: Annotated[Context, Depends(get_context)],
    user_claims: Annotated[UserClaims, Depends(require_authenticated_user)],
    topic_id: UUID,
    limit: Annotated[int, Query(ge=1, le=MAX_STORY_LIMIT)] = DEFAULT_STORY_LIMIT,
) -> list[StoryResponse]:
    # Reading is cheap and side-effect free: it returns stories already produced
    # by the scheduler. Fetching new stories (the expensive path) happens only
    # on schedule, never here.
    topic = await context.topics.get(str(topic_id))
    if topic is None or topic.user_id != user_claims.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found",
        )

    stories = await context.stories.find(
        {"type": "story", "topic_id": str(topic_id)},
        sort=[{"created_at": "desc"}],
        limit=limit,
    )
    return [StoryResponse.of(story) for story in stories]
