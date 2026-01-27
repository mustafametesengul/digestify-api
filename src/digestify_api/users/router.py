from typing import Annotated

from fastapi import APIRouter, Depends

from digestify_api.auth import Auth, get_auth
from digestify_api.users.dependencies import get_user_service
from digestify_api.users.service import UserService

user_router = APIRouter(
    prefix="/user",
    tags=["user"],
)


@user_router.post("/register", status_code=201)
async def register(
    auth: Annotated[Auth, Depends(get_auth)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> None:
    await user_service.register(auth.id)
