from datetime import datetime
from typing import Annotated

from fastapi import Depends
from pydantic import BaseModel

from digestify_api.identity.dependencies import (
    Context,
    Unauthenticated,
    get_context,
    require_registered_user,
)
from digestify_api.identity.routers import api_router
from digestify_api.identity.token_generation import UserClaims


class AccountDetailsResponse(BaseModel):
    username: str | None
    created_at: datetime


@api_router.get("/account-details")
async def get_account_details(
    context: Annotated[Context, Depends(get_context)],
    user_claims: Annotated[UserClaims, Depends(require_registered_user)],
) -> AccountDetailsResponse:
    user = await context.user_repository.find_by_id(user_claims.id)

    if user is None:
        raise Unauthenticated()

    return AccountDetailsResponse(username=user.username, created_at=user.created_at)
