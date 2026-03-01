from datetime import datetime, timezone
from typing import Annotated
from uuid import uuid4

from asyncpg import UniqueViolationError
from fastapi import APIRouter, Depends

from digestify_api import infrastructure
from digestify_api.identity import (
    dependencies,
    exceptions,
    password,
    queries,
    schemas,
    tokens,
)

router = APIRouter()


@router.post("/sign_in_anonymously", status_code=201)
async def sign_in_anonymously(
    token_manager: Annotated[
        tokens.TokenManager, Depends(dependencies.get_token_manager)
    ],
) -> schemas.Token:
    user_claims = schemas.UserClaims(
        id=uuid4(),
        is_anonymous=True,
    )
    return token_manager.generate(user_claims)


@router.post("/sign_up_with_username", status_code=201)
async def sign_up_with_username(
    database: Annotated[infrastructure.Database, Depends(dependencies.get_database)],
    token_manager: Annotated[
        tokens.TokenManager, Depends(dependencies.get_token_manager)
    ],
    channel: Annotated[infrastructure.Channel, Depends(dependencies.get_channel)],
    payload: schemas.SignUpWithUsername,
) -> schemas.Token:
    async with database.transaction() as connection:
        now = datetime.now(timezone.utc)

        password_hash = await password.hash_password(payload.password)

        user = queries.User(
            id=uuid4(),
            username=payload.username,
            password_hash=password_hash,
            is_deleted=False,
            created_at=now,
            updated_at=None,
            version=1,
        )

        try:
            await queries.create_user(connection, user)
        except UniqueViolationError:
            raise exceptions.UserAlreadyExists()

        event = schemas.UserSignedUp(
            user_id=user.id,
            username=user.username,
            version=user.version,
        )

        await channel.save_event(connection, event)

        token_payload = schemas.UserClaims(id=user.id, is_anonymous=False)
        return token_manager.generate(token_payload)


@router.post("/sign_in_with_username")
async def sign_in_with_username(
    database: Annotated[infrastructure.Database, Depends(dependencies.get_database)],
    token_manager: Annotated[
        tokens.TokenManager, Depends(dependencies.get_token_manager)
    ],
    payload: schemas.SignInWithUsername,
) -> schemas.Token:
    async with database.transaction() as connection:
        user = await queries.get_user_by_username(connection, payload.username)
        if user is None or user.password_hash is None:
            raise exceptions.InvalidCredentials()

        password_valid = await password.verify_password(
            payload.password,
            user.password_hash,
        )

        if not password_valid:
            raise exceptions.InvalidCredentials()

        token_payload = schemas.UserClaims(id=user.id, is_anonymous=False)
        return token_manager.generate(token_payload)


@router.post("/refresh_token")
async def refresh_token(
    token_manager: Annotated[
        tokens.TokenManager, Depends(dependencies.get_token_manager)
    ],
    payload: schemas.RefreshToken,
) -> schemas.Token:
    token_payload = token_manager.decode(
        payload.refresh_token, purpose=tokens.TokenPurpose.REFRESH
    )

    return token_manager.generate(token_payload)


@router.post("/delete_account")
async def delete_account(
    database: Annotated[infrastructure.Database, Depends(dependencies.get_database)],
    channel: Annotated[infrastructure.Channel, Depends(dependencies.get_channel)],
    user_claims: Annotated[schemas.UserClaims, Depends(dependencies.get_user_claims)],
) -> None:
    async with database.transaction() as connection:
        now = datetime.now(timezone.utc)
        user = await queries.get_user(connection, user_claims.id, lock=True)
        user.is_deleted = True
        user.updated_at = now
        user.version += 1
        user.username = None
        user.password_hash = None
        await queries.update_user(connection, user)

        event = schemas.UserDeleted(
            user_id=user.id,
            version=user.version,
        )

        await channel.save_event(connection, event)
