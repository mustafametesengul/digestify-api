from typing import Annotated
from uuid import uuid4

from fastapi import Depends

from digestify_api.identity.dependencies import IdentityContext, get_context
from digestify_api.identity.routers import api_router
from digestify_api.identity.token_generation import TokenPair, UserClaims, UserRole


@api_router.post("/sign-in-anonymously", status_code=201)
async def sign_in_anonymously(
    context: Annotated[IdentityContext, Depends(get_context)],
) -> TokenPair:
    user_claims = UserClaims(id=uuid4(), role=UserRole.ANONYMOUS)
    return context.token_generator.generate(user_claims)
