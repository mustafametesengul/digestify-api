import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Annotated, Literal, override
from uuid import UUID

from pydantic import BaseModel, Field
from rillo import Aggregate

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


class State(BaseModel):
    email: str
    user_id: UUID | None
    challenge: Challenge | None
    last_issued_at: datetime


class SignInCodeIssued(BaseModel):
    type: Literal["SignInCodeIssuedV1"] = "SignInCodeIssuedV1"
    email: str
    code_hash: str
    issued_at: datetime
    expires_at: datetime


class SignInAttemptFailed(BaseModel):
    type: Literal["SignInAttemptFailedV1"] = "SignInAttemptFailedV1"


class SignInCompleted(BaseModel):
    type: Literal["SignInCompletedV1"] = "SignInCompletedV1"
    user_id: UUID


type Event = Annotated[
    SignInCodeIssued | SignInAttemptFailed | SignInCompleted,
    Field(discriminator="type"),
]


class SignInCode(Aggregate[State, Event]):
    def __init__(self, email: str) -> None:
        normalized = email.strip().lower()
        super().__init__(hashlib.sha256(normalized.encode()).hexdigest())
        self._email = normalized

    @property
    def email(self) -> str:
        return self._email

    def issue_code(self, code: str, now: datetime) -> None:
        if (
            self._state is not None
            and now - self._state.last_issued_at < ISSUE_COOLDOWN
        ):
            raise CodeRequestedTooSoon()
        self._emit(
            SignInCodeIssued(
                email=self._email,
                code_hash=self._hash_code(code),
                issued_at=now,
                expires_at=now + CODE_TIME_TO_LIVE,
            )
        )

    def verify_code(self, code: str, now: datetime) -> None:
        challenge = self._state.challenge if self._state is not None else None
        if (
            challenge is None
            or now >= challenge.expires_at
            or challenge.attempts_remaining <= 0
        ):
            raise InvalidCode()
        if not hmac.compare_digest(challenge.code_hash, self._hash_code(code)):
            self._emit(SignInAttemptFailed())
            raise InvalidCode()

    def complete(self, user_id: UUID) -> None:
        self._emit(SignInCompleted(user_id=user_id))

    def user_id(self) -> UUID | None:
        return self._state.user_id if self._state is not None else None

    def _hash_code(self, code: str) -> str:
        return hashlib.sha256(f"{self._email}:{code}".encode()).hexdigest()

    @override
    def apply(self, event: Event) -> None:
        match event:
            case SignInCodeIssued():
                self._state = State(
                    email=event.email,
                    user_id=self._state.user_id if self._state is not None else None,
                    challenge=Challenge(
                        code_hash=event.code_hash,
                        expires_at=event.expires_at,
                        attempts_remaining=MAX_VERIFICATION_ATTEMPTS,
                    ),
                    last_issued_at=event.issued_at,
                )
            case SignInAttemptFailed():
                if self._state is not None and self._state.challenge is not None:
                    self._state.challenge.attempts_remaining -= 1
            case SignInCompleted():
                if self._state is not None:
                    self._state.user_id = event.user_id
                    self._state.challenge = None
