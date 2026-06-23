from typing import Annotated

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from digestify_api.identity.exceptions import Unauthenticated, Unauthorized
from digestify_api.identity.service import Accounts
from digestify_api.identity.token import (
    TokenPurpose,
    TokenVerifier,
    UserClaims,
    UserRole,
)


def get_identity_service(request: Request) -> Accounts:
    return request.app.state.identity_service


def get_token_verifier(request: Request) -> TokenVerifier:
    return request.app.state.token_verifier


http_bearer = HTTPBearer()


def require_authenticated_user(
    token_verifier: Annotated[TokenVerifier, Depends(get_token_verifier)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(http_bearer)],
) -> UserClaims:
    token = credentials.credentials
    try:
        return token_verifier.verify(token, purpose=TokenPurpose.ACCESS)
    except jwt.PyJWTError:
        raise Unauthenticated()


def require_registered_user(
    user_claims: Annotated[UserClaims, Depends(require_authenticated_user)],
) -> UserClaims:
    if user_claims.role is UserRole.ANONYMOUS:
        raise Unauthorized()
    return user_claims


def require_admin_user(
    user_claims: Annotated[UserClaims, Depends(require_authenticated_user)],
) -> UserClaims:
    if user_claims.role is not UserRole.ADMIN:
        raise Unauthorized()
    return user_claims
