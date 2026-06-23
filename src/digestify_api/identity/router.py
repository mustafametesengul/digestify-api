from typing import Annotated

from fastapi import APIRouter, Depends, status

from digestify_api.identity.dependencies import get_service, require_registered_user
from digestify_api.identity.schemas import (
    AccountDetailsResponse,
    RefreshTokenRequest,
    SignInWithEmailRequest,
    SignInWithEmailResponse,
    VerifySignInCodeRequest,
)
from digestify_api.identity.service import Service

router = APIRouter()


@router.post("/refresh-token")
async def refresh_token(
    service: Annotated[Service, Depends(get_service)],
    payload: RefreshTokenRequest,
) -> TokenPair:
    return await service.refresh_token(payload)


@router.get("/account-details")
async def get_account_details(
    service: Annotated[Service, Depends(get_service)],
    user_claims: Annotated[UserClaims, Depends(require_registered_user)],
) -> AccountDetailsResponse:
    account = await service.get_account_details(user_claims)
    return account


@router.post("/delete-account", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    service: Annotated[Service, Depends(get_service)],
    user_claims: Annotated[UserClaims, Depends(require_registered_user)],
) -> None:
    await service.delete_account(user_claims)


@router.post("/sign-in-anonymously")
async def sign_in_anonymously(
    service: Annotated[Service, Depends(get_service)],
) -> TokenPair:
    return service.sign_in_anonymously()


@router.post("/sign-in-with-email", status_code=status.HTTP_202_ACCEPTED)
async def sign_in_with_email(
    service: Annotated[Service, Depends(get_service)],
    payload: SignInWithEmailRequest,
) -> SignInWithEmailResponse:
    response = await service.sign_in_with_email(payload)
    return response


@router.post("/verify-sign-in-code")
async def verify_sign_in_code(
    service: Annotated[Service, Depends(get_service)],
    payload: VerifySignInCodeRequest,
) -> TokenPair:
    return await service.verify_sign_in_code(payload)
