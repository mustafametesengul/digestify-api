from typing import Annotated

from fastapi import Depends, status

from digestify_api.identity.dependencies import (
    Context,
    Unauthenticated,
    get_context,
    require_registered_user,
)
from digestify_api.identity.routers import api_router
from digestify_api.identity.token_generation import UserClaims


@api_router.post("/delete-account", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    context: Annotated[Context, Depends(get_context)],
    user_claims: Annotated[UserClaims, Depends(require_registered_user)],
) -> None:
    user = await context.users.load(id=user_claims.id)
    if user is None or user.discarded:
        raise Unauthenticated()

    event = user.delete_account()
    await context.users.add_event(event)
