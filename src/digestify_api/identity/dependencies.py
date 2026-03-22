from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from digestify_api.identity.token_generation import (
    TokenGenerator,
    TokenPurpose,
    UserClaims,
)
from digestify_api.identity.token_verification import TokenVerifier
from digestify_api.infrastructure import Database


class Unauthorized(HTTPException):
    def __init__(self, detail: str = "Unauthorized") -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


@dataclass
class Context:
    database: Database
    token_generator: TokenGenerator
    token_verifier: TokenVerifier


def get_context(request: Request) -> Context:
    return request.app.state.identity_context


http_bearer = HTTPBearer()


def get_user_claims(
    context: Annotated[Context, Depends(get_context)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(http_bearer)],
) -> UserClaims:
    token = credentials.credentials
    try:
        return context.token_verifier.verify(token, purpose=TokenPurpose.ACCESS)
    except jwt.PyJWTError:
        raise Unauthorized("Invalid access token")
