from typing import Annotated

from fastapi import Depends, status

from digestify_api.identity.dependencies import (
    Context,
    get_context,
    require_registered_user,
)
from digestify_api.identity.routers import api_router
from digestify_api.infrastructure.token_generation import UserClaims


@api_router.post("/delete-account", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    context: Annotated[Context, Depends(get_context)],
    user_claims: Annotated[UserClaims, Depends(require_registered_user)],
) -> None:
    user = await context.users.get(str(user_claims.id))
    if user is None:
        return

    user.delete()
    await context.users.save(user)
