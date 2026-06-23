from typing import Annotated, Callable
from uuid import UUID

from fastapi import Depends, HTTPException, status
from pydantic import BaseModel

from digestify_api.infrastructure.database import DocumentConflict
from digestify_api.infrastructure.token_generation import UserClaims
from digestify_api.news.active_topics import (
    MAX_ACTIVE_TOPICS,
    ActiveTopicLimitExceeded,
    ActiveTopics,
)
from digestify_api.news.dependencies import (
    Context,
    get_context,
    require_authenticated_user,
)
from digestify_api.news.routers import api_router
from digestify_api.news.topic import (
    Language,
    Schedule,
    Topic,
)

# Optimistic-concurrency retries when writing a user's `ActiveTopics` document.
MAX_CONFLICT_RETRIES = 5


class CreateTopicRequest(BaseModel):
    name: str
    description: str
    language: Language
    schedule: Schedule


class UpdateTopicScheduleRequest(BaseModel):
    topic_id: UUID
    schedule: Schedule


class TopicRequest(BaseModel):
    topic_id: UUID


class TopicResponse(BaseModel):
    id: UUID
    name: str
    description: str
    language: Language
    is_active: bool
    schedule: Schedule

    @classmethod
    def of(cls, topic: Topic, *, is_active: bool) -> "TopicResponse":
        return cls(
            id=UUID(topic.id),
            name=topic.name,
            description=topic.description,
            language=topic.language,
            is_active=is_active,
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


async def _is_active(context: Context, user_id: UUID, topic_id: UUID) -> bool:
    activation = await context.active_topics.get(ActiveTopics.id_for(user_id))
    return activation is not None and activation.is_active(topic_id)


async def _mutate_active_topics(
    context: Context, user_id: UUID, mutate: Callable[[ActiveTopics], None]
) -> None:
    """Read-modify-write the user's `ActiveTopics` under optimistic concurrency.

    `mutate` is applied to a freshly read document on every attempt, so the
    cap it enforces is always checked against the current set — two racing
    activations cannot both slip past `MAX_ACTIVE_TOPICS`. Exceptions raised by
    `mutate` (e.g. `ActiveTopicLimitExceeded`) happen before the write and
    propagate to the caller; only write conflicts are retried.
    """
    for _ in range(MAX_CONFLICT_RETRIES):
        activation = await context.active_topics.get(
            ActiveTopics.id_for(user_id)
        ) or ActiveTopics.for_user(user_id)
        mutate(activation)
        try:
            await context.active_topics.save(activation)
            return
        except DocumentConflict:
            continue  # another activation wrote concurrently; re-read and retry
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Active topics were modified concurrently, please retry",
    )


@api_router.post("/create-topic", status_code=status.HTTP_201_CREATED)
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

    # Activate the new topic automatically when the user is still below the
    # active-topic cap, so the common case needs no separate activate call. If
    # the cap is already reached the topic is simply left inactive.
    is_active = False
    try:
        await _mutate_active_topics(
            context, user_claims.id, lambda a: a.activate(UUID(topic.id))
        )
        is_active = True
    except ActiveTopicLimitExceeded:
        pass

    return TopicResponse.of(topic, is_active=is_active)


@api_router.post("/update-topic-schedule")
async def update_topic_schedule(
    context: Annotated[Context, Depends(get_context)],
    user_claims: Annotated[UserClaims, Depends(require_authenticated_user)],
    payload: UpdateTopicScheduleRequest,
) -> TopicResponse:
    topic = await _owned_topic(payload.topic_id, user_claims, context)
    topic.update_schedule(payload.schedule)
    await _save(context, topic)
    is_active = await _is_active(context, user_claims.id, UUID(topic.id))
    return TopicResponse.of(topic, is_active=is_active)


@api_router.post("/activate-topic")
async def activate_topic(
    context: Annotated[Context, Depends(get_context)],
    user_claims: Annotated[UserClaims, Depends(require_authenticated_user)],
    payload: TopicRequest,
) -> TopicResponse:
    topic = await _owned_topic(payload.topic_id, user_claims, context)

    try:
        await _mutate_active_topics(
            context, user_claims.id, lambda a: a.activate(UUID(topic.id))
        )
    except ActiveTopicLimitExceeded:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"At most {MAX_ACTIVE_TOPICS} topics can be active at once; "
                "deactivate one first"
            ),
        )

    return TopicResponse.of(topic, is_active=True)


@api_router.post("/deactivate-topic")
async def deactivate_topic(
    context: Annotated[Context, Depends(get_context)],
    user_claims: Annotated[UserClaims, Depends(require_authenticated_user)],
    payload: TopicRequest,
) -> TopicResponse:
    topic = await _owned_topic(payload.topic_id, user_claims, context)
    await _mutate_active_topics(
        context, user_claims.id, lambda a: a.deactivate(UUID(topic.id))
    )
    return TopicResponse.of(topic, is_active=False)
