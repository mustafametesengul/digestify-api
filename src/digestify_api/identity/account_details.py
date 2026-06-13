from typing import Annotated

from fastapi import Depends, HTTPException, status
from pydantic import BaseModel

from digestify_api.identity.dependencies import (
    Context,
    get_context,
    require_registered_user,
)
from digestify_api.identity.routers import api_router
from digestify_api.identity.token_generation import UserClaims


class AccountDetailsResponse(BaseModel):
    email: str


@api_router.get("/account-details")
async def get_account_details(
    context: Annotated[Context, Depends(get_context)],
    user_claims: Annotated[UserClaims, Depends(require_registered_user)],
) -> AccountDetailsResponse:
    user = await context.users.get(str(user_claims.id))
    if user is None or not user.is_active():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    return AccountDetailsResponse(email=user.email)
