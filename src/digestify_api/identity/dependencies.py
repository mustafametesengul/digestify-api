from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from digestify_api.identity.token_generation import (
    TokenGenerator,
    TokenPurpose,
    UserClaims,
    UserRole,
)
from digestify_api.identity.token_verification import TokenVerifier
from digestify_api.infrastructure import Database


class Unauthenticated(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


class Unauthorized(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action",
        )


@dataclass
class Context:
    database: Database
    token_generator: TokenGenerator
    token_verifier: TokenVerifier


def get_context(request: Request) -> Context:
    return request.app.state.identity_context


http_bearer = HTTPBearer()


def require_authenticated_user(
    context: Annotated[Context, Depends(get_context)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(http_bearer)],
) -> UserClaims:
    token = credentials.credentials
    try:
        return context.token_verifier.verify(token, purpose=TokenPurpose.ACCESS)
    except jwt.PyJWTError:
        raise Unauthenticated()


def require_registered_user(
    user_claims: Annotated[UserClaims, Depends(require_authenticated_user)],
) -> UserClaims:
    if user_claims.role is UserRole.ANONYMOUS:
        raise Unauthorized()
    return user_claims
