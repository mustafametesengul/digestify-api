from typing import Annotated

from fastapi import Depends
from pydantic import BaseModel

from digestify_api.identity.dependencies import Context, get_context
from digestify_api.identity.routers import api_router
from digestify_api.identity.token_generation import Token, TokenPurpose


class RefreshTokenRequest(BaseModel):
    refresh_token: str


@api_router.post("/refresh-token")
async def refresh_token(
    context: Annotated[Context, Depends(get_context)],
    payload: RefreshTokenRequest,
) -> Token:
    user_claims = context.token_verifier.verify(
        payload.refresh_token,
        purpose=TokenPurpose.REFRESH,
    )
    return context.token_generator.generate(user_claims)
