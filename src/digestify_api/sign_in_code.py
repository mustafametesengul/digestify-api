import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from digestify_api.couchdb import Document, Database

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


class VerifiedCode(BaseModel):
    email: str
    user_id: UUID | None


class InvalidCode(Exception):
    pass


class CodeRequestedTooSoon(Exception):
    pass


class SignInCodeService:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def init(self) -> None:
        await self._database.ensure_database()
        await self._database.ensure_index(
            fields=["email"],
            name="sign_in_code_email_index",
        )

    @staticmethod
    def _id_for(email: str) -> str:
        return hashlib.sha256(email.strip().lower().encode()).hexdigest()

    async def issue(self, email: str) -> tuple[str, str]:
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

        return sign_in.email, code

    async def verify(self, email: str, code: str) -> VerifiedCode:
        sign_in = await self._database.get(SignInCode, self._id_for(email))
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

        return VerifiedCode(email=sign_in.email, user_id=sign_in.user_id)

    async def link_user(self, email: str, user_id: UUID) -> None:
        sign_in = await self._database.get(SignInCode, self._id_for(email))
        if sign_in is None:
            raise InvalidCode()

        sign_in.user_id = user_id
        sign_in.challenge = None
        await self._database.save(sign_in)


__all__ = ["SignInCodeService", "InvalidCode", "CodeRequestedTooSoon"]
