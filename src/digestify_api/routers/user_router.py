from typing import Annotated

from fastapi import APIRouter, Depends

from digestify_api.auth import Auth, get_auth
from digestify_api.exceptions import UserAlreadyExists
from digestify_api.models import SubscriptionTier, UserCreate
from digestify_api.repositories import UserRepository

user_router = APIRouter(
    prefix="/user",
    tags=["user"],
)


@user_router.post("/register", status_code=201)
async def register(
    auth: Annotated[Auth, Depends(get_auth)],
    user_repository: Annotated[UserRepository, Depends()],
) -> None:
    user_exists = await user_repository.user_exists(auth.id)
    if user_exists:
        raise UserAlreadyExists()

    user = UserCreate(
        id=auth.id,
        discarded=False,
        subscription_tier=SubscriptionTier.FREE,
        created_topics_count=0,
        followed_topics_count=0,
    )

    await user_repository.create_user(user)
