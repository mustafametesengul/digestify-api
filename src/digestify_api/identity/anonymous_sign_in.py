from typing import Annotated

from fastapi import Depends

from digestify_api.identity.dependencies import Context, get_context
from digestify_api.identity.routers import api_router
from digestify_api.identity.token_generation import Token, UserClaims, UserRole


@api_router.post("/sign-in-anonymously", status_code=201)
async def sign_in_anonymously(
    context: Annotated[Context, Depends(get_context)],
) -> Token:
    user_claims = UserClaims(role=UserRole.ANONYMOUS)
    return context.token_generator.generate(user_claims)
