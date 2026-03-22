from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from digestify_api.identity import (
    TokenPurpose,
    TokenVerifier,
    Unauthorized,
    UserClaims,
    UserRole,
)
from digestify_api.infrastructure import Database


@dataclass
class Context:
    database: Database
    token_verifier: TokenVerifier


def get_context(request: Request) -> Context:
    return request.app.state.news_context


http_bearer = HTTPBearer()


def get_user_claims(
    context: Annotated[Context, Depends(get_context)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(http_bearer)],
) -> UserClaims:
    token = credentials.credentials
    try:
        user_claims = context.token_verifier.verify(token, purpose=TokenPurpose.ACCESS)
    except jwt.PyJWTError:
        raise Unauthorized("Invalid access token")

    if user_claims.role is UserRole.ANONYMOUS:
        raise Unauthorized("Anonymous users are not allowed to perform this action")

    return user_claims
