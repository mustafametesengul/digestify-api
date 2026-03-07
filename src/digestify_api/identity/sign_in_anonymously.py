from typing import Annotated
from uuid import uuid4

from fastapi import Depends

from digestify_api.identity.bootstrap import router
from digestify_api.identity.tokens import (
    Token,
    TokenManager,
    UserClaims,
    get_token_manager,
)


@router.post("/sign_in_anonymously", status_code=201)
async def sign_in_anonymously(
    token_manager: Annotated[TokenManager, Depends(get_token_manager)],
) -> Token:
    user_claims = UserClaims(
        id=uuid4(),
        is_anonymous=True,
    )
    return token_manager.generate(user_claims)
