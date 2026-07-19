from typing import AsyncIterator
from uuid import uuid4

import jwt

from digestify_api.email import EmailSender
from digestify_api.sign_in_code import (
    CodeRequestedTooSoon,
    InvalidCode,
    SignInCodeService,
)
from digestify_api.token import (
    TokenGenerator,
    TokenPair,
    TokenPurpose,
    TokenVerifier,
    UserClaims,
    UserRole,
)
from digestify_api.user import User, UserService


class Identity:
    def __init__(
        self,
        user_service: UserService,
        sign_in_code_service: SignInCodeService,
        email_sender: EmailSender,
        token_generator: TokenGenerator,
        token_verifier: TokenVerifier,
    ) -> None:
        self._users = user_service
        self._sign_in_codes = sign_in_code_service
        self._email_sender = email_sender
        self._token_generator = token_generator
        self._token_verifier = token_verifier

    async def init(self) -> None:
        await self._users.init()
        await self._sign_in_codes.init()

    async def refresh_token_pair(self, refresh_token: str) -> TokenPair:
        user_claims = self._token_verifier.verify(
            refresh_token,
            purpose=TokenPurpose.REFRESH,
        )

        if user_claims.role is not UserRole.ANONYMOUS:
            if await self._users.get(user_claims.id) is None:
                raise jwt.InvalidTokenError()

        return self._token_generator.generate(user_claims)

    async def get_email(self, user_claims: UserClaims) -> str:
        user = await self._users.get(user_claims.id)
        if user is None:
            raise jwt.InvalidTokenError()

        return user.email

    async def delete_account(self, user_claims: UserClaims) -> None:
        if not await self._users.delete(user_claims.id):
            raise jwt.InvalidTokenError()

    def sign_in_anonymously(self) -> TokenPair:
        user_claims = UserClaims(id=uuid4(), role=UserRole.ANONYMOUS)
        return self._token_generator.generate(user_claims)

    async def sign_in_with_email(self, email: str) -> None:
        recipient, code = await self._sign_in_codes.issue(email)

        await self._email_sender.send(
            to=recipient,
            subject="Your Digestify sign-in code",
            text=(
                f"Your Digestify sign-in code is {code}.\n\n"
                "It expires in 10 minutes. If you did not request this code, "
                "you can safely ignore this email."
            ),
        )

    async def verify_sign_in_code(self, email: str, code: str) -> TokenPair:
        verified = await self._sign_in_codes.verify(email, code)

        user_id = verified.user_id
        if user_id is not None and await self._users.get(user_id) is None:
            user_id = None

        if user_id is None:
            user_id = uuid4()
            await self._users.create(user_id, verified.email)

        await self._sign_in_codes.link_user(verified.email, user_id)

        token_payload = UserClaims(id=user_id, role=UserRole.PERMANENT)
        return self._token_generator.generate(token_payload)


__all__ = ["Identity", "InvalidCode", "CodeRequestedTooSoon"]
