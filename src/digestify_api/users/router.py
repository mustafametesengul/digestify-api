from typing import Annotated

from fastapi import APIRouter, Depends

from digestify_api.auth import Auth, get_auth
from digestify_api.billing.router import (
    create_user as create_billing_user,
)
from digestify_api.billing.router import (
    delete_user as delete_billing_user,
)
from digestify_api.db import AsyncSession, get_session
from digestify_api.following.router import (
    create_user as create_following_user,
)
from digestify_api.following.router import (
    delete_user as delete_following_user,
)

router = APIRouter(
    prefix="/users",
    tags=["users"],
)


@router.post("/user")
async def create_user(
    auth: Annotated[Auth, Depends(get_auth)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    await create_billing_user(session=session, user_id=auth.id)
    await create_following_user(session=session, user_id=auth.id)


@router.delete("/user")
async def delete_user(
    auth: Annotated[Auth, Depends(get_auth)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    await delete_billing_user(session=session, user_id=auth.id)
    await delete_following_user(session=session, user_id=auth.id)
