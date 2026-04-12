from datetime import UTC, datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, TypeAdapter

from digestify_api.infrastructure.event_store import (
    Command,
    Entity,
    Event,
    mutates_entity,
)


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


UserEvent = Annotated[UserSignedUp | AccountDeleted, Field(discriminator="type")]
user_event_adapter = TypeAdapter(UserEvent)


class User(Entity):
    type: Literal["User"] = "User"
    username: str | None
    password_hash: str | None
    created_at: datetime

    @classmethod
    def on_user_signed_up(cls, event: UserSignedUp) -> Self:
        return cls(
            id=event.entity_id,
            version=event.entity_version,
            username=event.username,
            password_hash=event.password_hash,
            created_at=event.created_at,
        )

    def on_account_deleted(self, event: AccountDeleted) -> None:
        self.discarded = True
        self.version = event.entity_version

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
