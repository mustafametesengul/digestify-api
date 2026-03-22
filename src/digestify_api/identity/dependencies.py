from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from digestify_api.identity.token_generation import TokenGenerator, UserClaims
from digestify_api.identity.token_verification import TokenVerifier
from digestify_api.infrastructure import Database


@dataclass
class IdentityContext:
    database: Database
    token_generator: TokenGenerator
    token_verifier: TokenVerifier


def get_context(request: Request) -> IdentityContext:
    return request.app.state.identity_context


http_bearer = HTTPBearer()


def get_user_claims(
    context: Annotated[IdentityContext, Depends(get_context)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(http_bearer)],
) -> UserClaims:
    token = credentials.credentials
    return context.token_verifier.verify(token)
