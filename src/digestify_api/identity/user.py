from typing import Literal
from uuid import UUID

from digestify_api.infrastructure import Entity, Event, Command


class SignUpWithUsername(Command):
    type: Literal["SignUpWithUsername"] = "SignUpWithUsername"
    user_id: UUID
    username: str
    password_hash: str


class UserSignedUp(Event):
    type: Literal["UserSignedUp"] = "UserSignedUp"
    username: str
    password_hash: str


class AccountDeleted(Event):
    type: Literal["AccountDeleted"] = "AccountDeleted"


class User(Entity):
    type: Literal["User"] = "User"
    username: str | None
    password_hash: str | None

    @staticmethod
    def sign_up_with_username(command: SignUpWithUsername) -> UserSignedUp:
        return UserSignedUp(
            entity_id=command.user_id,
            entity_version=1,
            username=command.username,
            password_hash=command.password_hash,
        )

    def delete_account(self) -> AccountDeleted:
        return AccountDeleted(entity_id=self.id, entity_version=self.version)

    def apply_user_signed_up(self, event: UserSignedUp) -> None:
        self.username = event.username
        self.password_hash = event.password_hash

    def apply_account_deleted(self, _: AccountDeleted) -> None:
        self.username = None
        self.password_hash = None
