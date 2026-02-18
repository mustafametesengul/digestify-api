from datetime import datetime, timezone
from typing import Annotated
from uuid import uuid4

from asyncpg import UniqueViolationError
from fastapi import APIRouter, Depends

from digestify_api.auth.dependencies import get_database
from digestify_api.auth.exceptions import UserAlreadyExists
from digestify_api.auth.models import (
    RefreshTokenRequest,
    SignInWithUsernameRequest,
    SignUpWithUsernameRequest,
    User,
    UserSignedUp,
)
from digestify_api.auth.password import hash_password, verify_password
from digestify_api.auth.queries import create_user, get_user_by_username
from digestify_api.db import Database
from digestify_api.jwt import (
    InvalidCredentials,
    JWTService,
    TokenPayload,
    TokenResponse,
    TokenType,
    get_jwt_service,
)
from digestify_api.messaging import Message, create_message

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/sign_in_anonymously", status_code=201)
async def sign_in_anonymously(
    jwt_manager: Annotated[JWTService, Depends(get_jwt_service)],
) -> TokenResponse:
    auth = TokenPayload(
        id=uuid4(),
        is_anonymous=True,
    )
    return jwt_manager.generate_tokens(auth)


@router.post("/sign_up_with_username", status_code=201)
async def sign_up_with_username(
    database: Annotated[Database, Depends(get_database)],
    jwt_manager: Annotated[JWTService, Depends(get_jwt_service)],
    payload: SignUpWithUsernameRequest,
) -> TokenResponse:
    now = datetime.now(timezone.utc)

    async with database.transaction() as connection:
        password_hash = await hash_password(payload.password)

        user = User(
            id=uuid4(),
            username=payload.username,
            password_hash=password_hash,
            discarded=False,
            created_at=now,
            updated_at=None,
            version=1,
        )

        try:
            await create_user(connection, user)
        except UniqueViolationError:
            raise UserAlreadyExists()

        event = UserSignedUp(
            user_id=user.id,
            username=user.username,
            version=user.version,
        )

        message = Message(
            id=uuid4(),
            type="UserSignedUpEvent",
            destination="auth-events",
            payload=event.model_dump_json(),
            created_at=now,
            scheduled_at=now,
        )
        await create_message(connection, message)

        auth = TokenPayload(id=user.id, is_anonymous=False)
        return jwt_manager.generate_tokens(auth)


@router.post("/sign_in_with_username")
async def sign_in_with_username(
    database: Annotated[Database, Depends(get_database)],
    jwt_manager: Annotated[JWTService, Depends(get_jwt_service)],
    payload: SignInWithUsernameRequest,
) -> TokenResponse:
    async with database.transaction() as connection:
        user = await get_user_by_username(connection, payload.username)
        if user is None or user.password_hash is None:
            raise InvalidCredentials()

        password_valid = await verify_password(
            payload.password,
            user.password_hash,
        )

        if not password_valid:
            raise InvalidCredentials()

        auth = TokenPayload(id=user.id, is_anonymous=False)
        return jwt_manager.generate_tokens(auth)


@router.post("/refresh_token")
async def refresh_token(
    jwt_manager: Annotated[JWTService, Depends(get_jwt_service)],
    payload: RefreshTokenRequest,
) -> TokenResponse:
    auth = jwt_manager.decode_token(payload.refresh_token, token_type=TokenType.REFRESH)

    return jwt_manager.generate_tokens(auth)
