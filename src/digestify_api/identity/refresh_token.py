from typing import Annotated

from fastapi import Depends
from pydantic import BaseModel

from digestify_api.identity.context import IdentityContext
from digestify_api.identity.dependencies import get_context, router
from digestify_api.identity.token_manager import Token, TokenPurpose


class RefreshToken(BaseModel):
    refresh_token: str


@router.post("/refresh_token")
async def refresh_token(
    context: Annotated[IdentityContext, Depends(get_context)],
    payload: RefreshToken,
) -> Token:
    token_payload = context.token_manager.decode(
        payload.refresh_token, purpose=TokenPurpose.REFRESH
    )

    return context.token_manager.generate(token_payload)
