from datetime import datetime, timezone
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends

from digestify_api import dependencies, exceptions, models, queries

router = APIRouter(
    prefix="/users",
    tags=["users"],
)


@router.post("/sign_up_with_username", status_code=201)
async def sign_up_with_username(
    request: models.users.SignUpWithUsernameRequest,
    db_manager: Annotated[dependencies.db.DBManager, Depends(dependencies.db.get_db)],
    auth_manager: Annotated[
        dependencies.auth.AuthManager, Depends(dependencies.auth.get_auth_manager)
    ],
) -> None:
    now = datetime.now(timezone.utc)

    async with db_manager.get_connection() as connection:
        existing_user = await queries.users.get_by_username(
            connection, request.username
        )
        if existing_user:
            raise exceptions.users.UserAlreadyExists()

        password_hash = await auth_manager.get_password_hash(request.password)

        user = models.users.User(
            id=uuid4(),
            username=request.username,
            password_hash=password_hash,
            discarded=False,
            tier=models.users.UserTier.FREE,
            created_topics_count=0,
            followed_topics_count=0,
            created_at=now,
            updated_at=None,
        )

        await queries.users.create(connection, user)


@router.post("/sign_in_anonymously", status_code=201)
async def sign_in_anonymously(
    db_manager: Annotated[dependencies.db.DBManager, Depends(dependencies.db.get_db)],
    auth_manager: Annotated[
        dependencies.auth.AuthManager, Depends(dependencies.auth.get_auth_manager)
    ],
) -> models.auth.Token:
    now = datetime.now(timezone.utc)

    async with db_manager.get_connection() as connection:
        user = models.users.User(
            id=uuid4(),
            username=None,
            password_hash=None,
            discarded=False,
            tier=models.users.UserTier.ANONYMOUS,
            created_topics_count=0,
            followed_topics_count=0,
            created_at=now,
            updated_at=None,
        )

        await queries.users.create(connection, user)

    access_token = auth_manager.create_access_token({"sub": str(user.id)})
    refresh_token = auth_manager.create_refresh_token({"sub": str(user.id)})
    return models.auth.Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/sign_in_with_username")
async def sign_in_with_username(
    request: models.users.SignInWithUsernameRequest,
    db_manager: Annotated[dependencies.db.DBManager, Depends(dependencies.db.get_db)],
    auth_manager: Annotated[
        dependencies.auth.AuthManager, Depends(dependencies.auth.get_auth_manager)
    ],
) -> models.auth.Token:
    async with db_manager.get_connection() as connection:
        user = await queries.users.get_by_username(connection, request.username)
        if user is None or user.password_hash is None:
            raise exceptions.auth.InvalidCredentials()

        password_valid = await auth_manager.verify_password(
            request.password,
            user.password_hash,
        )

        if not password_valid:
            raise exceptions.auth.InvalidCredentials()

        access_token = auth_manager.create_access_token({"sub": str(user.id)})
        refresh_token = auth_manager.create_refresh_token({"sub": str(user.id)})
        return models.auth.Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh_token")
async def refresh_token(
    request: models.auth.RefreshTokenRequest,
    auth_manager: Annotated[
        dependencies.auth.AuthManager, Depends(dependencies.auth.get_auth_manager)
    ],
) -> models.auth.Token:
    payload = auth_manager.verify_jwt_token(request.refresh_token)
    user_id = payload.get("sub")
    if not user_id:
        raise exceptions.auth.InvalidCredentials()

    access_token = auth_manager.create_access_token({"sub": user_id})
    refresh_token = auth_manager.create_refresh_token({"sub": user_id})

    return models.auth.Token(access_token=access_token, refresh_token=refresh_token)
