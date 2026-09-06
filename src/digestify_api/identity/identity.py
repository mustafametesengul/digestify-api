from datetime import UTC, datetime
from uuid import UUID, uuid4

import jwt

from digestify_api.couchdb import DocumentConflict, Repository
from digestify_api.identity.email import EmailClient
from digestify_api.identity.sign_in_code import (
    CodeRequestedTooSoon,
    InvalidCode,
    SignInCode,
)
from digestify_api.identity.token import (
    TokenClaims,
    TokenGenerator,
    TokenPair,
    TokenPurpose,
    TokenVerifier,
    UserClaims,
    UserRole,
)
from digestify_api.identity.user import User


class Identity:
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
        """Renew a reusable refresh token without writing authentication state."""
        user_claims = self._token_verifier.verify(
            refresh_token,
            purpose=TokenPurpose.REFRESH,
        )

        await self.validate_user(user_claims)
        return self._token_generator.generate(user_claims)

    async def validate_user(self, user_claims: UserClaims) -> None:
        if user_claims.role is not UserRole.ANONYMOUS:
            await self._get_authorized_user(user_claims)

    async def _get_authorized_user(self, claims: UserClaims) -> User:
        user = await self._get_user(claims.id)
        if (
            user is None
            or claims.role is UserRole.ANONYMOUS
            or claims.token_generation != user.token_generation
        ):
            raise jwt.InvalidTokenError()
        return user

    async def authorize(self, claims: TokenClaims) -> None:
        """Check observed account state; revocation propagates with replication."""
        await self.validate_user(claims)

    async def get_email(self, user_claims: UserClaims) -> str:
        user = await self._get_authorized_user(user_claims)
        return user.email

    async def delete_account(self, user_claims: UserClaims) -> None:
        user = await self._get_authorized_user(user_claims)
        user.delete()
        await self._users.save(user)

    async def sign_in_anonymously(self) -> TokenPair:
        user_claims = UserClaims(id=uuid4(), role=UserRole.ANONYMOUS)
        return self._token_generator.generate(user_claims)

    async def sign_in_with_email(self, email: str) -> None:
        sign_in = await self._sign_in_codes.get(SignInCode.id_for(email))
        if sign_in is None:
            sign_in = SignInCode.for_email(email)

        code = sign_in.issue(datetime.now(UTC))
        try:
            await self._sign_in_codes.save(sign_in)
        except DocumentConflict as error:
            raise CodeRequestedTooSoon() from error

        await self._email_sender.send(
            to=sign_in.email,
            subject="Your Digestify sign-in code",
            text=(
                f"Your Digestify sign-in code is {code}.\n\n"
                "It expires in 10 minutes. If you did not request this code, "
                "you can safely ignore this email."
            ),
        )

    async def verify_sign_in_code(
        self, email: str, code: str, *, revoke_tokens: bool = False
    ) -> TokenPair:
        """Provision a reserved account and consume the challenge before issuing tokens."""
        for _ in range(5):
            try:
                return await self._verify_sign_in_code(
                    email, code, revoke_tokens=revoke_tokens
                )
            except DocumentConflict:
                continue
        raise InvalidCode()

    async def _verify_sign_in_code(
        self, email: str, code: str, *, revoke_tokens: bool
    ) -> TokenPair:
        sign_in = await self._sign_in_codes.get(SignInCode.id_for(email))
        if sign_in is None:
            raise InvalidCode()

        try:
            sign_in.verify(code, datetime.now(UTC))
        except InvalidCode:
            # A wrong guess consumed an attempt; persist that before failing.
            await self._sign_in_codes.save(sign_in)
            raise

        user = (
            await self._users.get(str(sign_in.user_id))
            if sign_in.user_id is not None
            else None
        )
        if sign_in.user_id is None or (user is not None and user.is_deleted):
            sign_in.reserve_user()
            await self._sign_in_codes.save(sign_in)
            user = None
        user_id = sign_in.user_id
        assert user_id is not None
        if user is not None and user.email != sign_in.email:
            raise InvalidCode()
        if user is None:
            user = User.create(user_id, sign_in.email)
            await self._users.save(user)

        sign_in.link_user(user_id)
        await self._sign_in_codes.save(sign_in)

        if revoke_tokens:
            user.revoke_tokens()
            await self._users.save(user)

        user_claims = UserClaims(
            id=user_id, role=UserRole.PERMANENT, token_generation=user.token_generation
        )
        return self._token_generator.generate(user_claims)

    async def _get_user(self, user_id: UUID) -> User | None:
        user = await self._users.get(str(user_id))
        if user is None or user.is_deleted:
            return None
        return user
