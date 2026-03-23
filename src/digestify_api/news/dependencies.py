from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from digestify_api.identity import (
    TokenPurpose,
    TokenVerifier,
    Unauthenticated,
    UserClaims,
    UserRole,
)
from digestify_api.identity.dependencies import Unauthorized
from digestify_api.infrastructure import Database


@dataclass
class Context:
    database: Database
    token_verifier: TokenVerifier


def get_context(request: Request) -> Context:
    return request.app.state.news_context


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
