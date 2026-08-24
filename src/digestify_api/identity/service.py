from datetime import UTC, datetime
from uuid import UUID, uuid4

import jwt

from digestify_api.couchdb import Repository
from digestify_api.identity.email import EmailClient
from digestify_api.identity.sign_in_code import InvalidCode, SignInCode
from digestify_api.identity.token import (
    TokenGenerator,
    TokenPair,
    TokenPurpose,
    TokenVerifier,
    UserClaims,
    UserRole,
)
from digestify_api.identity.user import User


class Service:
    def __init__(
        self,
        users: Repository[User],
        sign_in_codes: Repository[SignInCode],
        email_sender: EmailClient,
        token_generator: TokenGenerator,
        token_verifier: TokenVerifier,
    ) -> None:
        self._users = users
        self._sign_in_codes = sign_in_codes
        self._email_sender = email_sender
        self._token_generator = token_generator
        self._token_verifier = token_verifier

    async def refresh_token_pair(self, refresh_token: str) -> TokenPair:
        user_claims = self._token_verifier.verify(
            refresh_token,
            purpose=TokenPurpose.REFRESH,
        )

        if user_claims.role is not UserRole.ANONYMOUS:
            if await self._get_user(user_claims.id) is None:
                raise jwt.InvalidTokenError()

        return self._token_generator.generate(user_claims)

    async def get_email(self, user_claims: UserClaims) -> str:
        user = await self._get_user(user_claims.id)
        if user is None:
            raise jwt.InvalidTokenError()

        return user.email

    async def delete_account(self, user_claims: UserClaims) -> None:
        user = await self._get_user(user_claims.id)
        if user is None:
            raise jwt.InvalidTokenError()

        user.delete()
        await self._users.save(user)

    def sign_in_anonymously(self) -> TokenPair:
        user_claims = UserClaims(id=uuid4(), role=UserRole.ANONYMOUS)
        return self._token_generator.generate(user_claims)

    async def sign_in_with_email(self, email: str) -> None:
        sign_in = await self._sign_in_codes.get(SignInCode.id_for(email))
        if sign_in is None:
            sign_in = SignInCode.for_email(email)

        code = sign_in.issue(datetime.now(UTC))
        await self._sign_in_codes.save(sign_in)

        await self._email_sender.send(
            to=sign_in.email,
            subject="Your Digestify sign-in code",
            text=(
                f"Your Digestify sign-in code is {code}.\n\n"
                "It expires in 10 minutes. If you did not request this code, "
                "you can safely ignore this email."
            ),
        )

    async def verify_sign_in_code(self, email: str, code: str) -> TokenPair:
        sign_in = await self._sign_in_codes.get(SignInCode.id_for(email))
        if sign_in is None:
            raise InvalidCode()

        try:
            sign_in.verify(code, datetime.now(UTC))
        except InvalidCode:
            # A wrong guess consumed an attempt; persist that before failing.
            await self._sign_in_codes.save(sign_in)
            raise

        user_id = sign_in.user_id
        if user_id is not None and await self._get_user(user_id) is None:
            user_id = None

        if user_id is None:
            user_id = uuid4()
            await self._users.save(User.create(user_id, sign_in.email))

        sign_in.link_user(user_id)
        await self._sign_in_codes.save(sign_in)

        user_claims = UserClaims(id=user_id, role=UserRole.PERMANENT)
        return self._token_generator.generate(user_claims)

    async def _get_user(self, user_id: UUID) -> User | None:
        user = await self._users.get(str(user_id))
        if user is None or user.is_deleted:
            return None
        return user
