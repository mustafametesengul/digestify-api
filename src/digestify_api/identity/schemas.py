from pydantic import BaseModel, EmailStr, Field

from digestify_api.identity.accounts import CODE_LENGTH


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class AccountDetailsResponse(BaseModel):
    email: str


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
