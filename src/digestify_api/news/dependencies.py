from dataclasses import dataclass
from typing import Annotated

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
class NewsContext:
    database: Database
    token_verifier: TokenVerifier


def get_context(request: Request) -> NewsContext:
    return request.app.state.news_context


http_bearer = HTTPBearer()


def get_user_claims(
    context: Annotated[NewsContext, Depends(get_context)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(http_bearer)],
) -> UserClaims:
    token = credentials.credentials
    user_claims = context.token_verifier.verify(token, purpose=TokenPurpose.ACCESS)
    if user_claims.role is UserRole.ANONYMOUS:
        raise Unauthorized("Invalid access token")
    return user_claims
