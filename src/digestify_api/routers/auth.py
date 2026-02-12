from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends

from digestify_api import dependencies, exceptions, models, queries

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


@router.post("/sign_up_with_username", status_code=201)
async def sign_up_with_username(
    db_manager: Annotated[
        dependencies.db.DBManager,
        Depends(dependencies.db.get_db_manager),
    ],
    auth_manager: Annotated[
        dependencies.auth.AuthManager,
        Depends(dependencies.auth.get_auth_manager),
    ],
    payload: models.auth.SignUpWithUsernameRequest,
) -> None:
    now = datetime.now(timezone.utc)

    async with db_manager.get_connection() as connection:
        user_exists = await queries.users.exists_by_username(
            connection, payload.username
        )
        if user_exists:
            raise exceptions.users.UserAlreadyExists()

        password_hash = await auth_manager.hash_password(payload.password)

        user = models.users.User(
            id=uuid4(),
            username=payload.username,
            password_hash=password_hash,
            discarded=False,
            tier=models.users.UserTier.FREE,
            active_topics_count=0,
            created_topics_count=0,
            followed_topics_count=0,
            created_at=now,
            updated_at=None,
            tier_last_confirmed_at=now,
        )

        await queries.users.create(connection, user)

        task_schedule = now + timedelta(days=5)
        task_payload = models.users.CheckUserTierTask(user_id=user.id)

        new_task = models.tasks.Task(
            id=uuid4(),
            name="check_user_tier",
            payload=task_payload.model_dump_json(),
            created_at=now,
            updated_at=None,
            scheduled_at=task_schedule,
            status=models.tasks.TaskStatus.PENDING,
            error_message=None,
        )
        await queries.tasks.create(connection, new_task)


@router.post("/sign_in_anonymously", status_code=201)
async def sign_in_anonymously(
    db_manager: Annotated[
        dependencies.db.DBManager,
        Depends(dependencies.db.get_db_manager),
    ],
    auth_manager: Annotated[
        dependencies.auth.AuthManager,
        Depends(dependencies.auth.get_auth_manager),
    ],
) -> models.auth.TokenResponse:
    auth = models.auth.Auth(
        id=uuid4(),
        is_anonymous=True,
    )
    return auth_manager.create_tokens(auth)


@router.post("/sign_in_with_username")
async def sign_in_with_username(
    db_manager: Annotated[
        dependencies.db.DBManager,
        Depends(dependencies.db.get_db_manager),
    ],
    auth_manager: Annotated[
        dependencies.auth.AuthManager,
        Depends(dependencies.auth.get_auth_manager),
    ],
    payload: models.auth.SignInWithUsernameRequest,
) -> models.auth.TokenResponse:
    async with db_manager.get_connection() as connection:
        user = await queries.users.get_by_username(connection, payload.username)
        if user is None or user.password_hash is None:
            raise exceptions.auth.InvalidCredentials()

        password_valid = await auth_manager.verify_password(
            payload.password,
            user.password_hash,
        )

        if not password_valid:
            raise exceptions.auth.InvalidCredentials()

        auth = models.auth.Auth(id=user.id, is_anonymous=False)
        return auth_manager.create_tokens(auth)


@router.post("/refresh_token")
async def refresh_token(
    auth_manager: Annotated[
        dependencies.auth.AuthManager,
        Depends(dependencies.auth.get_auth_manager),
    ],
    payload: models.auth.RefreshTokenRequest,
) -> models.auth.TokenResponse:
    auth = auth_manager.verify_jwt_token(payload.refresh_token, token_type="refresh")

    return auth_manager.create_tokens(auth)
