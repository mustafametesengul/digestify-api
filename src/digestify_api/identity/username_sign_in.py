from typing import Annotated

from fastapi import Depends
from pydantic import BaseModel, Field

from digestify_api.identity.dependencies import (
    Context,
    Unauthenticated,
    get_context,
)
from digestify_api.identity.password import verify_password
from digestify_api.identity.routers import api_router
from digestify_api.identity.token_generation import TokenPair, UserClaims, UserRole


class SignInWithUsernameRequest(BaseModel):
    username: str = Field(..., min_length=4, max_length=32)
    password: str = Field(..., min_length=8, max_length=64)


DUMMY_PASSWORD_HASH = "$2b$12$0X2yM4eQk9nO7/tOaG0E4u.NlXY7.sTq/.w.0B891gA2t2Tf0E1/O"


@api_router.post("/sign-in-with-username")
async def sign_in_with_username(
    context: Annotated[Context, Depends(get_context)],
    payload: SignInWithUsernameRequest,
) -> TokenPair:
    user = await context.user_repository.find_by_username(payload.username)

    password_valid = False
    if user is None or user.is_discarded or user.password_hash is None:
        await verify_password(payload.password, DUMMY_PASSWORD_HASH)
    else:
        password_valid = await verify_password(
            payload.password,
            user.password_hash,
        )
    if not password_valid or user is None:
        raise Unauthenticated(detail="Incorrect username or password")

    token_payload = UserClaims(id=user.id, role=UserRole.PERMANENT)
    return context.token_generator.generate(token_payload)
