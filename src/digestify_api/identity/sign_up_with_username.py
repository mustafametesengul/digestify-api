from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID, uuid4

from asyncpg import UniqueViolationError
from fastapi import Depends, HTTPException, status
from pydantic import BaseModel, Field

from digestify_api.identity.context import Context
from digestify_api.identity.dependencies import get_context, message_router, router
from digestify_api.identity.password import hash_password
from digestify_api.identity.token_manager import Token, UserClaims
from digestify_api.identity.user import User, create_user
from digestify_api.infrastructure import Event, enqueue_message


class SignUpWithUsername(BaseModel):
    username: str = Field(..., min_length=4, max_length=32)
    password: str = Field(..., min_length=8)


class UserSignedUp(Event):
    user_id: UUID
    username: str | None
    version: int


class UserAlreadyExists(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already exists",
        )


@router.post("/sign_up_with_username", status_code=201)
async def sign_up_with_username(
    context: Annotated[Context, Depends(get_context)],
    payload: SignUpWithUsername,
) -> Token:
    async with context.database.transaction() as connection:
        now = datetime.now(timezone.utc)

        password_hash = await hash_password(payload.password)

        user = User(
            id=uuid4(),
            username=payload.username,
            password_hash=password_hash,
            is_deleted=False,
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

        await enqueue_message(message_router.events, connection, event)

        token_payload = UserClaims(id=user.id, is_anonymous=False)
        return context.token_manager.generate(token_payload)
