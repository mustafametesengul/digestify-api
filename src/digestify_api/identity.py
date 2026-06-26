import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import AsyncIterator, Literal
from uuid import UUID, uuid4

import jwt
from pydantic import BaseModel

from digestify_api.token import (
    TokenGenerator,
    TokenPair,
    TokenPurpose,
    TokenVerifier,
    UserClaims,
    UserRole,
)
from digestify_api.couchdb import Document, Database
from digestify_api.email import EmailSender

CODE_LENGTH = 6
CODE_TIME_TO_LIVE = timedelta(minutes=10)
ISSUE_COOLDOWN = timedelta(seconds=60)
MAX_VERIFICATION_ATTEMPTS = 5


class Challenge(BaseModel):
    code_hash: str
    expires_at: datetime
    attempts_remaining: int


class SignInCode(Document):
    type: Literal["sign_in_code"] = "sign_in_code"
    email: str
    user_id: UUID | None = None
    challenge: Challenge | None = None
    last_issued_at: datetime | None = None


class User(Document):
    type: Literal["user"] = "user"
    email: str
    is_deleted: bool = False


class InvalidCode(Exception):
    pass


class CodeRequestedTooSoon(Exception):
    pass


class Identity:
    def __init__(
        self,
        database: Database,
        email_sender: EmailSender,
        token_generator: TokenGenerator,
        token_verifier: TokenVerifier,
    ):
        self._database = database
        self._email_sender = email_sender
        self._token_generator = token_generator
        self._token_verifier = token_verifier

    async def init(self) -> None:
        await self._database.ensure_database()
        await self._database.ensure_index(
            fields=["email"],
            name="sign_in_code_email_index",
        )
        await self._database.ensure_index(
            fields=["email"],
            name="user_email_index",
        )

    async def refresh_token_pair(self, refresh_token: str) -> TokenPair:
        user_claims = self._token_verifier.verify(
            refresh_token,
            purpose=TokenPurpose.REFRESH,
        )

        if user_claims.role is not UserRole.ANONYMOUS:
            user = await self._database.get(User, str(user_claims.id))
            if user is None or user.is_deleted:
                raise jwt.InvalidTokenError()

        return self._token_generator.generate(user_claims)

    async def get_email(self, user_claims: UserClaims) -> str:
        user = await self._database.get(User, str(user_claims.id))
        if user is None or user.is_deleted:
            raise jwt.InvalidTokenError()

        return user.email

    async def delete_account(self, user_claims: UserClaims) -> None:
        user = await self._database.get(User, str(user_claims.id))
        if user is None or user.is_deleted:
            raise jwt.InvalidTokenError()

        user.is_deleted = True
        await self._database.save(user)

    def sign_in_anonymously(self) -> TokenPair:
        user_claims = UserClaims(id=uuid4(), role=UserRole.ANONYMOUS)
        return self._token_generator.generate(user_claims)

    async def sign_in_with_email(self, email: str) -> None:
        normalized = email.strip().lower()
        sign_in_id = hashlib.sha256(normalized.encode()).hexdigest()

        sign_in = await self._database.get(SignInCode, sign_in_id)
        if sign_in is None:
            sign_in = SignInCode(id=sign_in_id, email=normalized)

        now = datetime.now(UTC)
        if (
            sign_in.last_issued_at is not None
            and now - sign_in.last_issued_at < ISSUE_COOLDOWN
        ):
            raise CodeRequestedTooSoon()

        code = f"{secrets.randbelow(10**CODE_LENGTH):0{CODE_LENGTH}d}"
        sign_in.challenge = Challenge(
            code_hash=hashlib.sha256(f"{sign_in.email}:{code}".encode()).hexdigest(),
            expires_at=now + CODE_TIME_TO_LIVE,
            attempts_remaining=MAX_VERIFICATION_ATTEMPTS,
        )
        sign_in.last_issued_at = now
        await self._database.save(sign_in)

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
        sign_in_id = hashlib.sha256(email.strip().lower().encode()).hexdigest()
        sign_in = await self._database.get(SignInCode, sign_in_id)
        if sign_in is None:
            raise InvalidCode()

        now = datetime.now(UTC)
        challenge = sign_in.challenge
        try:
            if (
                challenge is None
                or now >= challenge.expires_at
                or challenge.attempts_remaining <= 0
            ):
                raise InvalidCode()
            code_hash = hashlib.sha256(f"{sign_in.email}:{code}".encode()).hexdigest()
            if not hmac.compare_digest(challenge.code_hash, code_hash):
                challenge.attempts_remaining -= 1
                raise InvalidCode()
        except InvalidCode:
            await self._database.save(sign_in)
            raise

        user_id = sign_in.user_id
        if user_id is not None:
            user = await self._database.get(User, str(user_id))
            if user is None or user.is_deleted:
                user_id = None

        if user_id is None:
            user_id = uuid4()
            user = User(id=str(user_id), email=sign_in.email)
            await self._database.save(user)

        sign_in.user_id = user_id
        sign_in.challenge = None
        await self._database.save(sign_in)

        token_payload = UserClaims(id=user_id, role=UserRole.PERMANENT)
        return self._token_generator.generate(token_payload)

    async def changes(self, since: str = "0") -> AsyncIterator[User]:
        async for change in self._database.changes(User, since=since):
            if isinstance(change.doc, User):
                yield change.doc


__all__ = ["Identity", "InvalidCode", "CodeRequestedTooSoon"]
