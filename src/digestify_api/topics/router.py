from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from digestify_api.auth import Auth, get_auth
from digestify_api.topics.dependencies import get_topic_service
from digestify_api.topics.service import TopicService

topic_router = APIRouter(
    prefix="/topic",
    tags=["topic"],
)


@topic_router.post("/create", status_code=201)
async def create_topic(
    auth: Annotated[Auth, Depends(get_auth)],
    topic_service: Annotated[TopicService, Depends(get_topic_service)],
    topic_id: UUID,
    name: str,
    description: str,
    language: str,
    image_url: str | None = None,
) -> None:
    await topic_service.create_topic(
        user_id=auth.id,
        topic_id=topic_id,
        name=name,
        description=description,
        language=language,
        image_url=image_url,
    )


@topic_router.post("/follow")
async def follow(
    auth: Annotated[Auth, Depends(get_auth)],
    topic_service: Annotated[TopicService, Depends(get_topic_service)],
    topic_id: UUID,
) -> None:
    await topic_service.follow(
        user_id=auth.id,
        topic_id=topic_id,
    )


@topic_router.post("/unfollow")
async def unfollow(
    auth: Annotated[Auth, Depends(get_auth)],
    topic_service: Annotated[TopicService, Depends(get_topic_service)],
    topic_id: UUID,
) -> None:
    await topic_service.unfollow(
        user_id=auth.id,
        topic_id=topic_id,
    )
