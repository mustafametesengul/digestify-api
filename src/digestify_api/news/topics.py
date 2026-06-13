from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from pydantic import BaseModel

from digestify_api.infrastructure.couchdb import DocumentConflict
from digestify_api.infrastructure.token_generation import UserClaims
from digestify_api.news.dependencies import (
    Context,
    get_context,
    require_authenticated_user,
)
from digestify_api.news.routers import api_router
from digestify_api.news.topic import (
    MAX_ACTIVE_TOPICS,
    Language,
    Schedule,
    Topic,
)


class CreateTopicRequest(BaseModel):
    name: str
    description: str
    language: Language
    schedule: Schedule


class TopicResponse(BaseModel):
    id: UUID
    name: str
    description: str
    language: Language
    is_active: bool
    schedule: Schedule

    @classmethod
    def of(cls, topic: Topic) -> "TopicResponse":
        return cls(
            id=UUID(topic.id),
            name=topic.name,
            description=topic.description,
            language=topic.language,
            is_active=topic.is_active,
            schedule=topic.schedule,
        )


async def _owned_topic(
    topic_id: UUID, user_claims: UserClaims, context: Context
) -> Topic:
    topic = await context.topics.get(str(topic_id))
    if topic is None or topic.user_id != user_claims.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found",
        )
    return topic


async def _save(context: Context, topic: Topic) -> None:
    try:
        await context.topics.save(topic)
    except DocumentConflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Topic was modified concurrently, please retry",
        )


@api_router.post("/topics", status_code=status.HTTP_201_CREATED)
async def create_topic(
    context: Annotated[Context, Depends(get_context)],
    user_claims: Annotated[UserClaims, Depends(require_authenticated_user)],
    payload: CreateTopicRequest,
) -> TopicResponse:
    topic = Topic.create(
        user_id=user_claims.id,
        name=payload.name,
        description=payload.description,
        language=payload.language,
        schedule=payload.schedule,
    )
    await _save(context, topic)
    return TopicResponse.of(topic)


@api_router.put("/topics/{topic_id}/schedule")
async def update_topic_schedule(
    context: Annotated[Context, Depends(get_context)],
    user_claims: Annotated[UserClaims, Depends(require_authenticated_user)],
    topic_id: UUID,
    schedule: Schedule,
) -> TopicResponse:
    topic = await _owned_topic(topic_id, user_claims, context)
    topic.update_schedule(schedule)
    await _save(context, topic)
    return TopicResponse.of(topic)


@api_router.post("/topics/{topic_id}/activate")
async def activate_topic(
    context: Annotated[Context, Depends(get_context)],
    user_claims: Annotated[UserClaims, Depends(require_authenticated_user)],
    topic_id: UUID,
) -> TopicResponse:
    topic = await _owned_topic(topic_id, user_claims, context)

    if not topic.is_active:
        active = await context.topics.find(
            {"type": "topic", "user_id": str(user_claims.id), "is_active": True},
            limit=MAX_ACTIVE_TOPICS + 1,
        )
        if len(active) >= MAX_ACTIVE_TOPICS:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"At most {MAX_ACTIVE_TOPICS} topics can be active at once; "
                    "deactivate one first"
                ),
            )

    topic.activate()
    await _save(context, topic)
    return TopicResponse.of(topic)


@api_router.post("/topics/{topic_id}/deactivate")
async def deactivate_topic(
    context: Annotated[Context, Depends(get_context)],
    user_claims: Annotated[UserClaims, Depends(require_authenticated_user)],
    topic_id: UUID,
) -> TopicResponse:
    topic = await _owned_topic(topic_id, user_claims, context)
    topic.deactivate()
    await _save(context, topic)
    return TopicResponse.of(topic)
