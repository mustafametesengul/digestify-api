from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from rillo import Repository

from digestify_api.identity.email_delivery import EmailSender
from digestify_api.identity.sign_in_code import SignInCode
from digestify_api.identity.token_generation import (
    TokenGenerator,
    TokenPurpose,
    UserClaims,
    UserRole,
)
from digestify_api.identity.token_verification import TokenVerifier
from digestify_api.identity.user import User


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


@dataclass
class Context:
    users: Repository[User]
    sign_in_codes: Repository[SignInCode]
    email_sender: EmailSender
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


def require_admin_user(
    user_claims: Annotated[UserClaims, Depends(require_authenticated_user)],
) -> UserClaims:
    if user_claims.role is not UserRole.ADMIN:
        raise Unauthorized()
    return user_claims
