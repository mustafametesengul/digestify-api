from collections.abc import AsyncIterator
from typing import Annotated

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field

from digestify_api.couchdb import (
    DocumentConflict,
    UnresolvedDocumentConflict,
    WriteNotConfirmed,
)
from digestify_api.identity.email import EmailDeliveryError
from digestify_api.identity.identity import Identity
from digestify_api.identity.sign_in_code import (
    CODE_LENGTH,
    ISSUE_COOLDOWN,
    CodeRequestedTooSoon,
    InvalidCode,
)
from digestify_api.identity.token import (
    TokenPair,
    TokenPurpose,
    TokenVerifier,
    UserClaims,
    UserRole,
)

router = APIRouter(
    prefix="/identity",
    tags=["identity"],
)


class SignInWithEmailRequest(BaseModel):
    email: EmailStr


class SignInWithEmailResponse(BaseModel):
    detail: str = "A sign-in code has been sent to your email address"


class VerifySignInCodeRequest(BaseModel):
    email: EmailStr
    code: str = Field(
        default=...,
        min_length=CODE_LENGTH,
        max_length=CODE_LENGTH,
        pattern=r"^\d+$",
    )


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class AccountResponse(BaseModel):
    email: str


async def get_service(request: Request) -> AsyncIterator[Identity]:
    try:
        yield request.app.state.identity_service
    except (
        DocumentConflict,
        UnresolvedDocumentConflict,
        WriteNotConfirmed,
        httpx.HTTPError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Identity state is temporarily unavailable",
            headers={"Retry-After": "5"},
        ) from error


def get_token_verifier(request: Request) -> TokenVerifier:
    return request.app.state.identity_token_verifier


def _unauthenticated() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


# auto_error=False so a missing Authorization header becomes a 401 with a
# WWW-Authenticate challenge instead of HTTPBearer's default 403.
_http_bearer = HTTPBearer(auto_error=False)


async def require_user(
    service: Annotated[Identity, Depends(get_service)],
    token_verifier: Annotated[TokenVerifier, Depends(get_token_verifier)],
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_http_bearer),
    ],
) -> UserClaims:
    if credentials is None:
        raise _unauthenticated()

    try:
        claims = token_verifier.verify(
            credentials.credentials,
            purpose=TokenPurpose.ACCESS,
        )
        await service.authorize(claims)
        return claims
    except jwt.PyJWTError:
        raise _unauthenticated()


def require_registered_user(
    user_claims: Annotated[UserClaims, Depends(require_user)],
) -> UserClaims:
    if user_claims.role is UserRole.ANONYMOUS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires a registered account",
        )
    return user_claims


@router.post("/sign-in-anonymously")
async def sign_in_anonymously(
    service: Annotated[Identity, Depends(get_service)],
) -> TokenPair:
    return await service.sign_in_anonymously()


@router.post("/sign-in-with-email", status_code=status.HTTP_202_ACCEPTED)
async def sign_in_with_email(
    service: Annotated[Identity, Depends(get_service)],
    payload: SignInWithEmailRequest,
) -> SignInWithEmailResponse:
    try:
        await service.sign_in_with_email(payload.email)
    except CodeRequestedTooSoon:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="A sign-in code was requested recently; wait before retrying",
            headers={"Retry-After": str(int(ISSUE_COOLDOWN.total_seconds()))},
        )
    except EmailDeliveryError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to send the sign-in email",
        )
    return SignInWithEmailResponse()


@router.post("/verify-sign-in-code")
async def verify_sign_in_code(
    service: Annotated[Identity, Depends(get_service)],
    payload: VerifySignInCodeRequest,
) -> TokenPair:
    try:
        return await service.verify_sign_in_code(payload.email, payload.code)
    except InvalidCode:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired sign-in code",
        )


@router.post("/recover-account")
async def recover_account(
    service: Annotated[Identity, Depends(get_service)],
    payload: VerifySignInCodeRequest,
) -> TokenPair:
    """Verify email ownership, revoke all account tokens, and return a new pair."""
    try:
        return await service.verify_sign_in_code(
            payload.email, payload.code, revoke_tokens=True
        )
    except InvalidCode:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired sign-in code",
        )


@router.post("/refresh-token")
async def refresh_token(
    service: Annotated[Identity, Depends(get_service)],
    payload: RefreshTokenRequest,
) -> TokenPair:
    try:
        return await service.refresh_token_pair(payload.refresh_token)
    except jwt.PyJWTError:
        raise _unauthenticated()


@router.get("/account")
async def get_account(
    service: Annotated[Identity, Depends(get_service)],
    user_claims: Annotated[UserClaims, Depends(require_registered_user)],
) -> AccountResponse:
    try:
        email = await service.get_email(user_claims)
    except jwt.InvalidTokenError:
        raise _unauthenticated()
    return AccountResponse(email=email)


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    service: Annotated[Identity, Depends(get_service)],
    user_claims: Annotated[UserClaims, Depends(require_registered_user)],
) -> None:
    try:
        await service.delete_account(user_claims)
    except jwt.InvalidTokenError:
        raise _unauthenticated()
