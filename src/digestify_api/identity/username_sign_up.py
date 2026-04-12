from datetime import UTC, datetime
from typing import Annotated
from uuid import uuid7

from fastapi import Depends, HTTPException, status
from pydantic import BaseModel, Field

from digestify_api.identity.dependencies import Context, get_context
from digestify_api.identity.password import hash_password
from digestify_api.identity.routers import api_router
from digestify_api.identity.token_generation import TokenPair, UserClaims, UserRole
from digestify_api.identity.user import SignUpWithUsername, User


class SignUpWithUsernameRequest(BaseModel):
    username: str = Field(..., min_length=4, max_length=32)
    password: str = Field(..., min_length=8, max_length=64)


class UsernameAlreadyTaken(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )


@api_router.post("/sign-up-with-username", status_code=status.HTTP_201_CREATED)
async def sign_up_with_username(
    context: Annotated[Context, Depends(get_context)],
    payload: SignUpWithUsernameRequest,
) -> TokenPair:
    password_hash = await hash_password(payload.password)

    user_id = uuid7()

    event = User.sign_up_with_username(
        SignUpWithUsername(
            user_id=user_id,
            username=payload.username,
            password_hash=password_hash,
        )
    )
    await context.users.add_event(event)

    token_payload = UserClaims(id=user_id, role=UserRole.PERMANENT)
    return context.token_generator.generate(token_payload)
