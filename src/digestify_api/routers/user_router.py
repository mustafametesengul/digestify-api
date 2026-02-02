from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends

from digestify_api.dependencies import auth_manager, db_manager
from digestify_api.exceptions import auth_exceptions, users_exceptions
from digestify_api.models import auth_models, user_models
from digestify_api.queries import user_queries

router = APIRouter(
    prefix="/users",
    tags=["users"],
)


@router.post("/sign_up_with_username", status_code=201)
async def sign_up_with_username(
    request: user_models.SignUpWithUsernameRequest,
    db: Annotated[db_manager.DBManager, Depends(db_manager.get_db)],
    auth_manager: Annotated[
        auth_manager.AuthManager, Depends(auth_manager.get_auth_manager)
    ],
) -> user_models.UserResponse:
    now = datetime.now(timezone.utc)

    async with db.get_connection() as connection:
        existing_user = await user_queries.get_by_username(connection, request.username)
        if existing_user:
            raise users_exceptions.UserAlreadyExists()

        password_hash = await auth_manager.get_password_hash(request.password)

        user = user_models.User(
            id=request.user_id,
            username=request.username,
            password_hash=password_hash,
            discarded=False,
            tier=user_models.UserTier.FREE,
            created_topics_count=0,
            followed_topics_count=0,
            created_at=now,
            updated_at=None,
        )

        await user_queries.create(connection, user)
        return user_models.UserResponse.model_validate(user)


@router.post("/sign_up_anonymously", status_code=201)
async def sign_up_anonymously(
    request: user_models.SignUpAnonymouslyRequest,
    db: Annotated[db_manager.DBManager, Depends(db_manager.get_db)],
    auth_manager: Annotated[
        auth_manager.AuthManager, Depends(auth_manager.get_auth_manager)
    ],
) -> user_models.UserResponse:
    now = datetime.now(timezone.utc)

    async with db.get_connection() as connection:
        user = user_models.User(
            id=request.user_id,
            username=None,
            password_hash=None,
            discarded=False,
            tier=user_models.UserTier.ANONYMOUS,
            created_topics_count=0,
            followed_topics_count=0,
            created_at=now,
            updated_at=None,
        )

        await user_queries.create(connection, user)
        return user_models.UserResponse.model_validate(user)


@router.post("/sign_in_with_username")
async def sign_in_with_username(
    request: user_models.SignInWithUsernameRequest,
    db: Annotated[db_manager.DBManager, Depends(db_manager.get_db)],
    auth_manager: Annotated[
        auth_manager.AuthManager, Depends(auth_manager.get_auth_manager)
    ],
) -> auth_models.Token:
    async with db.get_connection() as connection:
        user = await user_queries.get_by_username(connection, request.username)
        if user is None or user.password_hash is None:
            raise auth_exceptions.InvalidCredentials()

        password_valid = await auth_manager.verify_password(
            request.password,
            user.password_hash,
        )

        if not password_valid:
            raise auth_exceptions.InvalidCredentials()

        access_token = auth_manager.create_access_token({"sub": str(user.id)})
        refresh_token = auth_manager.create_refresh_token({"sub": str(user.id)})
        return auth_models.Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh_token")
async def refresh_token(
    request: auth_models.RefreshTokenRequest,
    auth_manager: Annotated[
        auth_manager.AuthManager, Depends(auth_manager.get_auth_manager)
    ],
) -> auth_models.Token:
    payload = auth_manager.verify_jwt_token(request.refresh_token)
    user_id = payload.get("sub")
    if not user_id:
        raise auth_exceptions.InvalidCredentials()

    access_token = auth_manager.create_access_token({"sub": user_id})
    refresh_token = auth_manager.create_refresh_token({"sub": user_id})

    return auth_models.Token(access_token=access_token, refresh_token=refresh_token)
