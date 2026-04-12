from datetime import UTC, datetime
from typing import Literal, Self
from uuid import UUID

from digestify_api.infrastructure.event_store import Entity, Event, Command

from pydantic import BaseModel, Field, TypeAdapter
from typing import Annotated


class SignUpWithUsername(Command):
    type: Literal["SignUpWithUsername"] = "SignUpWithUsername"
    user_id: UUID
    username: str
    password_hash: str


class UserSignedUp(Event):
    type: Literal["UserSignedUp"] = "UserSignedUp"
    username: str
    password_hash: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AccountDeleted(Event):
    type: Literal["AccountDeleted"] = "AccountDeleted"


UserEventType = Annotated[UserSignedUp | AccountDeleted, Field(discriminator="type")]
user_event_adapter = TypeAdapter(UserEventType)


class User(Entity):
    type: Literal["User"] = "User"
    username: str | None
    password_hash: str | None
    created_at: datetime

    @staticmethod
    def sign_up_with_username(command: SignUpWithUsername) -> UserSignedUp:
        return UserSignedUp(
            entity_id=command.user_id,
            entity_version=1,
            username=command.username,
            password_hash=command.password_hash,
        )

    def delete_account(self) -> AccountDeleted:
        if self.discarded:
            raise ValueError("Account is already deleted.")
        return AccountDeleted(entity_id=self.id, entity_version=self.version)

    @classmethod
    def from_events(cls, events: list[UserEventType]) -> Self:
        user = None
        for e in events:
            if isinstance(e, UserSignedUp):
                user = cls(
                    id=e.entity_id,
                    version=e.entity_version,
                    username=e.username,
                    password_hash=e.password_hash,
                    created_at=e.created_at,
                )
            elif isinstance(e, AccountDeleted):
                if user is not None:
                    user.discarded = True
                    user.version = e.entity_version
                    user.username = None
                    user.password_hash = None

        if user is None:
            raise ValueError("No creation event found to apply.")
        return user

    @classmethod
    def from_events_json(cls, events_json: list[str]) -> Self:
        events = [user_event_adapter.validate_json(e) for e in events_json]
        return cls.from_events(events)
