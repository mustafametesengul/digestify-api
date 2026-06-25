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

from fastapi import HTTPException, status


class Unauthenticated(HTTPException):
    def __init__(self, detail: str = "Could not validate credentials") -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class Unauthorized(HTTPException):
    def __init__(
        self,
        detail: str = "You do not have permission to perform this action",
    ) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


class AccountNotFound(HTTPException):
    def __init__(
        self,
        detail: str = "The specified account does not exist",
    ) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
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
