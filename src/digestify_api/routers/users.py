from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends

from digestify_api.dependencies import DBManager, get_auth, get_db
from digestify_api.exceptions import UserAlreadyExists
from digestify_api.models import Auth, SubscriptionTier, User, UserPublic
from digestify_api.queries import create_user, user_exists

users_router = APIRouter(
    prefix="/users",
    tags=["users"],
)


@users_router.post("/register", status_code=201)
async def register(
    auth: Annotated[Auth, Depends(get_auth)],
    db: Annotated[DBManager, Depends(get_db)],
) -> UserPublic:
    now = datetime.now(timezone.utc)
    async with db.get_connection() as connection:
        user_exists_flag = await user_exists(connection, auth.id)
        if user_exists_flag:
            raise UserAlreadyExists()

        user = User(
            id=auth.id,
            discarded=False,
            subscription_tier=SubscriptionTier.FREE,
            created_topics_count=0,
            followed_topics_count=0,
            created_at=now,
            updated_at=None,
        )

        await create_user(connection, user)
        return UserPublic.model_validate(user)
