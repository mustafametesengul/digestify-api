from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from digestify_api.auth import Auth, get_auth
from digestify_api.billing.admin import (
    create_topic as create_billing_topic,
)
from digestify_api.billing.admin import (
    delete_topic as delete_billing_topic,
)
from digestify_api.db import AsyncSession, get_session
from digestify_api.following.admin import (
    create_topic as create_following_topic,
)
from digestify_api.following.admin import (
    delete_topic as delete_following_topic,
)

router = APIRouter(
    prefix="/topics",
    tags=["topics"],
)


@router.get("/topic")
async def create_topic(
    auth: Annotated[Auth, Depends(get_auth)],
    session: Annotated[AsyncSession, Depends(get_session)],
    topic_id: UUID,
) -> None:
    await create_billing_topic(
        session=session,
        user_id=auth.id,
        topic_id=topic_id,
    )
    await create_following_topic(
        session=session,
        user_id=auth.id,
        topic_id=topic_id,
    )


@router.delete("/topic")
async def delete_topic(
    auth: Annotated[Auth, Depends(get_auth)],
    session: Annotated[AsyncSession, Depends(get_session)],
    topic_id: UUID,
) -> None:
    await delete_billing_topic(
        session=session,
        user_id=auth.id,
        topic_id=topic_id,
    )
    await delete_following_topic(
        session=session,
        user_id=auth.id,
        topic_id=topic_id,
    )
