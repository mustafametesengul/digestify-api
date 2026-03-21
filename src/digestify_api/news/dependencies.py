from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from digestify_api.identity import TokenVerifier, UserClaims, UserRole
from digestify_api.infrastructure import Database


@dataclass
class Context:
    database: Database
    token_verifier: TokenVerifier


def get_context(request: Request) -> Context:
    return request.app.state.news_context


security = HTTPBearer()


class InvalidCredentials(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_user_claims(
    context: Annotated[Context, Depends(get_context)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> UserClaims:
    token = credentials.credentials
    user_claims = context.token_verifier.verify(token)
    if user_claims.role is UserRole.ANONYMOUS:
        raise InvalidCredentials()
    return user_claims
