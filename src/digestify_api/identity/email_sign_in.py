from typing import Annotated
from uuid import uuid4

from fastapi import Depends, status
from pydantic import BaseModel, Field

from digestify_api.identity.dependencies import Context, get_context
from digestify_api.identity.routers import api_router
from digestify_api.identity.token_generation import TokenPair, UserClaims, UserRole
from digestify_api.identity.user import User


class SignUpWithEmailRequest(BaseModel):
    email: str = Field(
        default=...,
        min_length=5,
        max_length=254,
        regex=r"^[^\s@]+@[^\s@]+\.[^\s@]+$",
    )


@api_router.post("/sign-up-with-email", status_code=status.HTTP_201_CREATED)
async def sign_up_with_email(
    context: Annotated[Context, Depends(get_context)],
    payload: SignUpWithEmailRequest,
) -> TokenPair:
    user_id = uuid4()
    user = User(user_id)

    await context.users.load(user)
    user.sign_up(email=payload.email)
    await context.users.save(user)

    token_payload = UserClaims(id=user_id, role=UserRole.PERMANENT)
    return context.token_generator.generate(token_payload)
