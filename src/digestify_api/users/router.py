from typing import Annotated

from fastapi import APIRouter, Depends

import digestify_api.following.router as following
import digestify_api.limits.router as billing
from digestify_api.auth import Auth, get_auth
from digestify_api.db import AsyncSession, get_session

users_router = APIRouter(
    prefix="/users",
    tags=["users"],
)


@users_router.post("/user")
async def create_user(
    session: Annotated[AsyncSession, Depends(get_session)],
    auth: Annotated[Auth, Depends(get_auth)],
) -> None:
    await billing.create_user(session=session, auth=auth)
    await following.create_user(session=session, auth=auth)


@users_router.delete("/user")
async def discard_user(
    session: Annotated[AsyncSession, Depends(get_session)],
    auth: Annotated[Auth, Depends(get_auth)],
) -> None:
    await billing.discard_user(session=session, auth=auth)
    await following.discard_user(session=session, auth=auth)
