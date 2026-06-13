from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from pydantic import BaseModel

from digestify_api.infrastructure.token_generation import UserClaims
from digestify_api.news.dependencies import (
    Context,
    get_context,
    require_authenticated_user,
)
from digestify_api.news.routers import api_router


class UserResponse(BaseModel):
    id: UUID


@api_router.get("/me")
async def get_user(
    context: Annotated[Context, Depends(get_context)],
    user_claims: Annotated[UserClaims, Depends(require_authenticated_user)],
) -> UserResponse:
    user = await context.users.get(str(user_claims.id))
    if user is None or not user.is_active():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserResponse(id=UUID(user.id))
