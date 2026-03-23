from typing import Annotated

import jwt
from fastapi import Depends
from pydantic import BaseModel

from digestify_api.identity.dependencies import (
    Context,
    Unauthenticated,
    get_context,
)
from digestify_api.identity.routers import api_router
from digestify_api.identity.token_generation import TokenPair, TokenPurpose, UserRole
from digestify_api.identity.user import get_user


class RefreshTokenRequest(BaseModel):
    refresh_token: str


@api_router.post("/refresh-token")
async def refresh_token(
    context: Annotated[Context, Depends(get_context)],
    payload: RefreshTokenRequest,
) -> TokenPair:
    try:
        user_claims = context.token_verifier.verify(
            payload.refresh_token,
            purpose=TokenPurpose.REFRESH,
        )
    except jwt.PyJWTError:
        raise Unauthenticated()

    if user_claims.role is not UserRole.ANONYMOUS:
        async with context.database.connection() as connection:
            user = await get_user(connection, user_claims.id)
            if user is None or user.is_deleted:
                raise Unauthenticated()

    return context.token_generator.generate(user_claims)
