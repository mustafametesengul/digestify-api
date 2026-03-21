from typing import Annotated

from fastapi import Depends
from pydantic import BaseModel

from digestify_api.identity.context import Context, get_context
from digestify_api.identity.router import router
from digestify_api.identity.token_generator import Token, TokenPurpose


class RefreshToken(BaseModel):
    refresh_token: str


@router.post("/refresh-token")
async def refresh_token(
    context: Annotated[Context, Depends(get_context)],
    payload: RefreshToken,
) -> Token:
    user_claims = context.token_decoder.decode(
        payload.refresh_token,
        purpose=TokenPurpose.REFRESH,
    )
    return context.token_generator.generate(user_claims)
