from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

import digestify_api.following.router as following
import digestify_api.limits.router as billing
from digestify_api.auth import Auth, get_auth
from digestify_api.db import AsyncSession, get_session

topics_router = APIRouter(
    prefix="/topics",
    tags=["topics"],
)


@topics_router.post("/topic")
async def create_topic(
    auth: Annotated[Auth, Depends(get_auth)],
    session: Annotated[AsyncSession, Depends(get_session)],
    topic_id: UUID,
) -> None:
    await billing.create_topic(
        session=session,
        auth=auth,
        topic_id=topic_id,
    )
    await following.create_topic(
        session=session,
        auth=auth,
        topic_id=topic_id,
    )


@topics_router.delete("/topic")
async def discard_topic(
    auth: Annotated[Auth, Depends(get_auth)],
    session: Annotated[AsyncSession, Depends(get_session)],
    topic_id: UUID,
) -> None:
    await billing.discard_topic(
        session=session,
        auth=auth,
        topic_id=topic_id,
    )
    await following.discard_topic(
        session=session,
        auth=auth,
        topic_id=topic_id,
    )
