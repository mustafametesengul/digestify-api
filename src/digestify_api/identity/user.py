from datetime import UTC, datetime
from typing import Annotated, Literal, Self
from uuid import UUID, uuid4

from pydantic import Field, TypeAdapter

from digestify_api.infrastructure.event_store import (
    Command,
    Entity,
    Event,
    command,
    classcommand,
    handler,
    classhandler,
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

    @classhandler
    @classmethod
    def on_user_signed_up(cls, event: UserSignedUp) -> Self:
        return cls(
            username=event.username,
            password_hash=event.password_hash,
        )

    @handler
    def on_account_deleted(self, event: AccountDeleted) -> None:
        self.discarded = True
        self.version = event.entity_version

    @classcommand
    @classmethod
    def sign_up_with_username(cls, command: SignUpWithUsername) -> UserSignedUp:
        return UserSignedUp(
            username=command.username,
            password_hash=command.password_hash,
        )

    @command
    def delete_account(self) -> AccountDeleted:
        if self.discarded:
            raise ValueError("Account is already deleted.")
        return AccountDeleted(entity_id=self.id, entity_version=self.version)


user = User(
    username="testuser",
    password_hash="hashedpassword",
    created_at=datetime.now(UTC),
)

user.delete_account()


z = User.sign_up_with_username(
    SignUpWithUsername(
        user_id=uuid4(),
        username="testuser",
        password_hash="hashedpassword",
    )
)

print(z)
