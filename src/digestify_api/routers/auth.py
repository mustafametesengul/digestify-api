from datetime import datetime, timezone
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends

from digestify_api.dependencies import AuthManager, DBManager, get_auth_manager, get_db
from digestify_api.exceptions import InvalidCredentials, UserAlreadyExists
from digestify_api.models import (
    SubscriptionTier,
    Token,
    TokenRefresh,
    User,
    UserLogin,
    UserPublic,
    UserRegister,
)
from digestify_api.queries import create_user, read_user_by_username

auth_router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


@auth_router.post("/register", status_code=201)
async def register(
    user_in: UserRegister,
    db: Annotated[DBManager, Depends(get_db)],
    auth_manager: Annotated[AuthManager, Depends(get_auth_manager)],
) -> UserPublic:
    now = datetime.now(timezone.utc)

    async with db.get_connection() as connection:
        existing_user = await read_user_by_username(connection, user_in.username)
        if existing_user:
            raise UserAlreadyExists()

        user = User(
            id=uuid4(),
            username=user_in.username,
            password_hash=await auth_manager.get_password_hash(user_in.password),
            discarded=False,
            subscription_tier=SubscriptionTier.FREE,
            created_topics_count=0,
            followed_topics_count=0,
            created_at=now,
            updated_at=None,
        )

        await create_user(connection, user)
        return UserPublic.model_validate(user)


@auth_router.post("/login")
async def login(
    login_in: UserLogin,
    db: Annotated[DBManager, Depends(get_db)],
    auth_manager: Annotated[AuthManager, Depends(get_auth_manager)],
) -> Token:
    async with db.get_connection() as connection:
        user = await read_user_by_username(connection, login_in.username)
        if not user or not await auth_manager.verify_password(
            login_in.password, user.password_hash
        ):
            raise InvalidCredentials()

        access_token = auth_manager.create_access_token({"sub": str(user.id)})
        refresh_token = auth_manager.create_refresh_token({"sub": str(user.id)})
        return Token(access_token=access_token, refresh_token=refresh_token)


@auth_router.post("/refresh")
async def refresh_token(
    refresh_in: TokenRefresh,
    auth_manager: Annotated[AuthManager, Depends(get_auth_manager)],
) -> Token:
    # Verify the refresh token
    payload = auth_manager.verify_jwt_token(refresh_in.refresh_token)
    user_id = payload.get("sub")
    if not user_id:
        raise InvalidCredentials()

    # Create new tokens
    access_token = auth_manager.create_access_token({"sub": user_id})
    refresh_token = auth_manager.create_refresh_token({"sub": user_id})

    return Token(access_token=access_token, refresh_token=refresh_token)
