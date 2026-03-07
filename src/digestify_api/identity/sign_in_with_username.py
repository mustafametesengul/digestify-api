from typing import Annotated

from fastapi import Depends, HTTPException, status
from pydantic import BaseModel, Field

from digestify_api.identity.bootstrap import get_database, router
from digestify_api.identity.password import verify_password
from digestify_api.identity.tokens import (
    Token,
    TokenManager,
    UserClaims,
    get_token_manager,
)
from digestify_api.identity.user import get_user_by_username
from digestify_api.infrastructure import Database


class SignInWithUsername(BaseModel):
    username: str = Field(..., min_length=4, max_length=32)
    password: str = Field(..., min_length=8)


class InvalidCredentials(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/sign_in_with_username")
async def sign_in_with_username(
    database: Annotated[Database, Depends(get_database)],
    token_manager: Annotated[TokenManager, Depends(get_token_manager)],
    payload: SignInWithUsername,
) -> Token:
    async with database.transaction() as connection:
        user = await get_user_by_username(connection, payload.username)
        if user is None or user.password_hash is None:
            raise InvalidCredentials()

        password_valid = await verify_password(
            payload.password,
            user.password_hash,
        )

        if not password_valid:
            raise InvalidCredentials()

        token_payload = UserClaims(id=user.id, is_anonymous=False)
        return token_manager.generate(token_payload)
