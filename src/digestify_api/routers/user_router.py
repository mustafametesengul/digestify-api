from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends

from digestify_api.auth import Auth, get_auth
from digestify_api.db import DBService, get_db
from digestify_api.exceptions.user_exceptions import UserAlreadyExists
from digestify_api.queries.user_queries import (
    SubscriptionTier,
    User,
    create_user,
    user_exists,
)

user_router = APIRouter(
    prefix="/user",
    tags=["user"],
)


@user_router.post("/register", status_code=201)
async def register(
    auth: Annotated[Auth, Depends(get_auth)],
    db: Annotated[DBService, Depends(get_db)],
) -> None:
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
