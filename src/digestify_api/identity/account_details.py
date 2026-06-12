from typing import Annotated

from fastapi import Depends
from pydantic import BaseModel

from digestify_api.identity.dependencies import (
    Context,
    get_context,
    require_registered_user,
)
from digestify_api.identity.routers import api_router
from digestify_api.identity.token_generation import UserClaims
from digestify_api.identity.user import User


class AccountDetailsResponse(BaseModel):
    email: str


@api_router.get("/account-details")
async def get_account_details(
    context: Annotated[Context, Depends(get_context)],
    user_claims: Annotated[UserClaims, Depends(require_registered_user)],
) -> AccountDetailsResponse:
    user = User(user_claims.id)
    await context.users.load(user)

    return AccountDetailsResponse(email=user.email())
