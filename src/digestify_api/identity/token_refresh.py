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
        user = await context.users.load(id=user_claims.id)
        if user is None or user.discarded:
            raise Unauthenticated()

    return context.token_generator.generate(user_claims)
