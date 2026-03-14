from typing import Annotated
from uuid import uuid4

from fastapi import Depends

from digestify_api.identity.context import IdentityContext
from digestify_api.identity.dependencies import get_context, router
from digestify_api.identity.token_manager import Token, UserClaims


@router.post("/sign_in_anonymously", status_code=201)
async def sign_in_anonymously(
    context: Annotated[IdentityContext, Depends(get_context)],
) -> Token:
    user_claims = UserClaims(
        id=uuid4(),
        is_anonymous=True,
    )
    return context.token_manager.generate(user_claims)
