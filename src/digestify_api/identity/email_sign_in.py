import secrets
from datetime import UTC, datetime
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from digestify_api.identity.dependencies import Context, get_context
from digestify_api.identity.email_delivery import EmailDeliveryError
from digestify_api.identity.routers import api_router
from digestify_api.identity.sign_in_code import (
    CODE_LENGTH,
    CodeRequestedTooSoon,
    InvalidCode,
    SignInCode,
)
from digestify_api.identity.user import User
from digestify_api.infrastructure.token_generation import (
    TokenPair,
    UserClaims,
    UserRole,
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


def _generate_code() -> str:
    return f"{secrets.randbelow(10**CODE_LENGTH):0{CODE_LENGTH}d}"


@api_router.post("/sign-in-with-email", status_code=status.HTTP_202_ACCEPTED)
async def sign_in_with_email(
    context: Annotated[Context, Depends(get_context)],
    payload: SignInWithEmailRequest,
) -> SignInWithEmailResponse:
    sign_in = await context.sign_in_codes.get(SignInCode.id_for(payload.email))
    if sign_in is None:
        sign_in = SignInCode.for_email(payload.email)

    code = _generate_code()
    try:
        sign_in.issue_code(code, now=datetime.now(UTC))
    except CodeRequestedTooSoon:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="A sign-in code was sent recently, wait before requesting another",
        )
    await context.sign_in_codes.save(sign_in)

    try:
        await context.email_sender.send(
            to=sign_in.email,
            subject="Your Digestify sign-in code",
            text=(
                f"Your Digestify sign-in code is {code}.\n\n"
                "It expires in 10 minutes. If you did not request this code, "
                "you can safely ignore this email."
            ),
        )
    except EmailDeliveryError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not send the sign-in email",
        )

    return SignInWithEmailResponse()


@api_router.post("/verify-sign-in-code")
async def verify_sign_in_code(
    context: Annotated[Context, Depends(get_context)],
    payload: VerifySignInCodeRequest,
) -> TokenPair:
    sign_in = await context.sign_in_codes.get(SignInCode.id_for(payload.email))
    if sign_in is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired sign-in code",
        )

    try:
        sign_in.verify_code(payload.code, now=datetime.now(UTC))
    except InvalidCode:
        await context.sign_in_codes.save(sign_in)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired sign-in code",
        )

    user_id = sign_in.user_id
    if user_id is not None:
        user = await context.users.get(str(user_id))
        if user is None or not user.is_active():
            user_id = None

    if user_id is None:
        user_id = uuid4()
        user = User.sign_up(user_id, email=sign_in.email)
        await context.users.save(user)

    sign_in.complete(user_id)
    await context.sign_in_codes.save(sign_in)

    token_payload = UserClaims(id=user_id, role=UserRole.PERMANENT)
    return context.token_generator.generate(token_payload)
