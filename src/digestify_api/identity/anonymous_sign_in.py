from typing import Annotated

from fastapi import Depends

from digestify_api.identity.context import Context, get_context
from digestify_api.identity.router import router
from digestify_api.identity.token_generator import Token, UserClaims, UserRole


@router.post("/sign_in_anonymously", status_code=201)
async def sign_in_anonymously(
    context: Annotated[Context, Depends(get_context)],
) -> Token:
    user_claims = UserClaims(role=UserRole.ANONYMOUS)
    return context.token_generator.generate(user_claims)
