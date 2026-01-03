from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import select

from digestify_api.auth import Auth, get_auth
from digestify_api.billing.exceptions import UserNotFound
from digestify_api.billing.models import User
from digestify_api.billing.schemas import UserRead
from digestify_api.db import AsyncSession, get_session

router = APIRouter(
    prefix="/billing",
    tags=["billing"],
)


@router.get("/user")
async def get_user(
    auth: Annotated[Auth, Depends(get_auth)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserRead:
    user_result = await session.exec(select(User).where(User.id == auth.id))
    user = user_result.one_or_none()
    if user is None:
        raise UserNotFound()
    return UserRead.model_validate(user.model_dump())
