import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from typing import Literal, Self
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import BaseModel

from digestify_api.couchdb import Document

CODE_LENGTH = 6
CODE_TIME_TO_LIVE = timedelta(minutes=10)
ISSUE_COOLDOWN = timedelta(seconds=60)
MAX_VERIFICATION_ATTEMPTS = 5


class InvalidCode(Exception):
    pass


class CodeRequestedTooSoon(Exception):
    pass


class Challenge(BaseModel):
    code_hash: str
    expires_at: datetime
    attempts_remaining: int


class SignInCode(Document):
    """The sign-in-code conversation for one email address.

    There is a single document per address — its id is a digest of the
    normalized email — so issuing a new code replaces any outstanding one.
    Mutating methods only change this document; the caller persists it, and
    must do so even when `verify` raises, since a wrong guess consumes an
    attempt. `user_id` may be reserved before its user document exists;
    provisioning retries must reuse that reservation. The challenge remains
    live until the user has been created and linked successfully.
    """

    type: Literal["sign_in_code"] = "sign_in_code"
    email: str
    user_id: UUID | None = None
    challenge: Challenge | None = None
    last_issued_at: datetime | None = None

    @staticmethod
    def id_for(email: str) -> str:
        return hashlib.sha256(_normalize(email).encode()).hexdigest()

    @classmethod
    def for_email(cls, email: str) -> Self:
        normalized = _normalize(email)
        return cls(id=cls.id_for(normalized), email=normalized)

    def issue(self, now: datetime) -> str:
        """Arm a fresh challenge and return its one-time code.

        Raises `CodeRequestedTooSoon` while the previous issue's cooldown is
        still running; the outstanding challenge stays valid in that case.
        """
        if (
            self.last_issued_at is not None
            and now - self.last_issued_at < ISSUE_COOLDOWN
        ):
            raise CodeRequestedTooSoon()

        code = f"{secrets.randbelow(10**CODE_LENGTH):0{CODE_LENGTH}d}"
        self.challenge = Challenge(
            code_hash=self._hash_code(code),
            expires_at=now + CODE_TIME_TO_LIVE,
            attempts_remaining=MAX_VERIFICATION_ATTEMPTS,
        )
        self.last_issued_at = now
        return code

    def verify(self, code: str, now: datetime) -> None:
        """Check `code` against the outstanding challenge.

        Raises `InvalidCode` when there is no live challenge or the code is
        wrong; a wrong code consumes an attempt.
        """
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

    def link_user(self, user_id: UUID) -> None:
        """Record the signed-in user and consume the challenge."""
        self.user_id = user_id
        self.challenge = None

    def reserve_user(self) -> UUID:
        """Derive the same next account ID on replicas with the same mapping."""
        self.user_id = uuid5(
            NAMESPACE_URL, f"digestify:account:{self.id}:{self.user_id or 'initial'}"
        )
        return self.user_id

    def _hash_code(self, code: str) -> str:
        return hashlib.sha256(f"{self.email}:{code}".encode()).hexdigest()


def _normalize(email: str) -> str:
    return email.strip().lower()
