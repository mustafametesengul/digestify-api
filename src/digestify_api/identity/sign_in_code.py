import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel

from digestify_api.infrastructure.couchdb import Document

CODE_LENGTH = 6
CODE_TIME_TO_LIVE = timedelta(minutes=10)
ISSUE_COOLDOWN = timedelta(seconds=60)
MAX_VERIFICATION_ATTEMPTS = 5


class CodeRequestedTooSoon(Exception):
    pass


class InvalidCode(Exception):
    pass


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

    @staticmethod
    def id_for(email: str) -> str:
        normalized = email.strip().lower()
        return hashlib.sha256(normalized.encode()).hexdigest()

    @classmethod
    def for_email(cls, email: str) -> Self:
        normalized = email.strip().lower()
        return cls(id=cls.id_for(normalized), email=normalized)

    def issue_code(self, code: str, now: datetime) -> None:
        if (
            self.last_issued_at is not None
            and now - self.last_issued_at < ISSUE_COOLDOWN
        ):
            raise CodeRequestedTooSoon()
        self.challenge = Challenge(
            code_hash=self._hash_code(code),
            expires_at=now + CODE_TIME_TO_LIVE,
            attempts_remaining=MAX_VERIFICATION_ATTEMPTS,
        )
        self.last_issued_at = now

    def verify_code(self, code: str, now: datetime) -> None:
        challenge = self.challenge
        if (
            challenge is None
            or now >= challenge.expires_at
            or challenge.attempts_remaining <= 0
        ):
            raise InvalidCode()
        if not hmac.compare_digest(challenge.code_hash, self._hash_code(code)):
            challenge.attempts_remaining -= 1
            raise InvalidCode()

    def complete(self, user_id: UUID) -> None:
        self.user_id = user_id
        self.challenge = None

    def _hash_code(self, code: str) -> str:
        return hashlib.sha256(f"{self.email}:{code}".encode()).hexdigest()
