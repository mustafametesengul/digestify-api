from datetime import datetime, timezone
from typing import Annotated
from uuid import uuid4

from asyncpg import UniqueViolationError
from fastapi import APIRouter, Depends

from digestify_api.identity import dependencies, exceptions, models, password, queries
from digestify_api.infrastructure import database, jwt

router = APIRouter()


@router.post("/sign_in_anonymously", status_code=201)
async def sign_in_anonymously(
    jwt_service: Annotated[jwt.JWTService, Depends(jwt.get_jwt_service)],
) -> jwt.TokenResponse:
    auth = jwt.TokenPayload(
        id=uuid4(),
        is_anonymous=True,
    )
    return jwt_service.generate_tokens(auth)


@router.post("/sign_up_with_username", status_code=201)
async def sign_up_with_username(
    db: Annotated[database.Database, Depends(dependencies.get_database)],
    jwt_service: Annotated[jwt.JWTService, Depends(jwt.get_jwt_service)],
    payload: models.SignUpWithUsernameRequest,
) -> jwt.TokenResponse:
    now = datetime.now(timezone.utc)

    async with db.transaction() as connection:
        password_hash = await password.hash_password(payload.password)

        user = models.User(
            id=uuid4(),
            username=payload.username,
            password_hash=password_hash,
            discarded=False,
            created_at=now,
            updated_at=None,
            version=1,
        )

        try:
            await queries.create_user(connection, user)
        except UniqueViolationError:
            raise exceptions.UserAlreadyExists()

        event = models.UserSignedUp(
            user_id=user.id,
            username=user.username,
            version=user.version,
        )

        await dependencies.channel.save_event(connection, event)

        auth = jwt.TokenPayload(id=user.id, is_anonymous=False)
        return jwt_service.generate_tokens(auth)


@router.post("/sign_in_with_username")
async def sign_in_with_username(
    db: Annotated[database.Database, Depends(dependencies.get_database)],
    jwt_service: Annotated[jwt.JWTService, Depends(jwt.get_jwt_service)],
    payload: models.SignInWithUsernameRequest,
) -> jwt.TokenResponse:
    async with db.transaction() as connection:
        user = await queries.get_user_by_username(connection, payload.username)
        if user is None or user.password_hash is None:
            raise jwt.InvalidCredentials()

        password_valid = await password.verify_password(
            payload.password,
            user.password_hash,
        )

        if not password_valid:
            raise jwt.InvalidCredentials()

        auth = jwt.TokenPayload(id=user.id, is_anonymous=False)
        return jwt_service.generate_tokens(auth)


@router.post("/refresh_token")
async def refresh_token(
    jwt_service: Annotated[jwt.JWTService, Depends(jwt.get_jwt_service)],
    payload: models.RefreshTokenRequest,
) -> jwt.TokenResponse:
    auth = jwt_service.decode_token(
        payload.refresh_token, token_type=jwt.TokenType.REFRESH
    )

    return jwt_service.generate_tokens(auth)
