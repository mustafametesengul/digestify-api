from collections.abc import AsyncIterator
from datetime import date
from typing import Annotated
from uuid import UUID

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from digestify_api.couchdb import (
    DocumentConflict,
    UnresolvedDocumentConflict,
    WriteNotConfirmed,
)
from digestify_api.identity.router import require_registered_user
from digestify_api.identity.token import UserClaims
from digestify_api.news.service import (
    RegisteredUserRequired,
    Service,
    TopicLimitReached,
    TopicNotFound,
)
from digestify_api.news.story import Story
from digestify_api.news.topic import Topic, TopicDetails

router = APIRouter(prefix="/news", tags=["news"])


class TopicRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic_id: UUID


class UpdateTopicRequest(TopicDetails):
    topic_id: UUID


class ListStoriesRequest(TopicRequest):
    before: date | None = None
    limit: int = Field(default=10, ge=1, le=100)


class UsageResponse(BaseModel):
    daily_limit: int = 5
    used: int


class StoryDay(BaseModel):
    day: date
    stories: list[Story]


async def get_service(request: Request) -> AsyncIterator[Service]:
    try:
        yield request.app.state.news_service
    except TopicNotFound:
        raise HTTPException(404, "Topic not found") from None
    except TopicLimitReached:
        raise HTTPException(409, "You can have at most five topics") from None
    except RegisteredUserRequired:
        raise HTTPException(403, "A registered account is required") from None
    except jwt.InvalidTokenError:
        raise HTTPException(
            401,
            "Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except (
        DocumentConflict,
        UnresolvedDocumentConflict,
        WriteNotConfirmed,
        httpx.HTTPError,
    ) as error:
        raise HTTPException(
            503,
            "Topic state is temporarily unavailable",
            headers={"Retry-After": "5"},
        ) from error


NewsService = Annotated[Service, Depends(get_service)]
RegisteredUser = Annotated[UserClaims, Depends(require_registered_user)]


@router.post("/create-topic", status_code=status.HTTP_201_CREATED)
async def create_topic(
    payload: TopicDetails, service: NewsService, claims: RegisteredUser
) -> Topic:
    return await service.create_topic(claims, payload)


@router.post("/list-topics")
async def list_topics(
    service: NewsService, claims: RegisteredUser
) -> list[Topic]:
    return await service.list_topics(claims)


@router.post("/get-usage")
async def get_usage(
    service: NewsService, claims: RegisteredUser
) -> UsageResponse:
    """Reservations consumed today (UTC), including failed AI attempts."""
    return UsageResponse(used=await service.get_usage(claims))


@router.post("/get-topic")
async def get_topic(
    payload: TopicRequest, service: NewsService, claims: RegisteredUser
) -> Topic:
    return await service.get_topic(claims, payload.topic_id)


@router.post("/update-topic")
async def update_topic(
    payload: UpdateTopicRequest,
    service: NewsService,
    claims: RegisteredUser,
) -> Topic:
    """Replace topic details without resetting daily usage."""
    details = TopicDetails.model_validate(
        payload.model_dump(exclude={"topic_id"})
    )
    return await service.update_topic(claims, payload.topic_id, details)


@router.post("/delete-topic", status_code=status.HTTP_204_NO_CONTENT)
async def delete_topic(
    payload: TopicRequest, service: NewsService, claims: RegisteredUser
) -> None:
    await service.delete_topic(claims, payload.topic_id)


@router.post("/list-stories")
async def list_stories(
    payload: ListStoriesRequest,
    service: NewsService,
    claims: RegisteredUser,
) -> list[StoryDay]:
    """Newest daily batches first; pass the last day as `before` to page."""
    batches = await service.list_stories(
        claims, payload.topic_id, before=payload.before, limit=payload.limit
    )
    return [
        StoryDay(day=batch.day, stories=batch.stories) for batch in batches
    ]
