from typing import Annotated

from fastapi import Depends
from pydantic import BaseModel

from digestify_api.identity.bootstrap import router
from digestify_api.identity.tokens import (
    Token,
    TokenManager,
    TokenPurpose,
    get_token_manager,
)


class RefreshToken(BaseModel):
    refresh_token: str


@router.post("/refresh_token")
async def refresh_token(
    token_manager: Annotated[TokenManager, Depends(get_token_manager)],
    payload: RefreshToken,
) -> Token:
    token_payload = token_manager.decode(
        payload.refresh_token, purpose=TokenPurpose.REFRESH
    )

    return token_manager.generate(token_payload)
