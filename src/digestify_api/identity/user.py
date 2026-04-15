from typing import Literal
from pydantic import BaseModel

from digestify_api.infrastructure.aggregate import Aggregate, mutator


class UserSignedUp(BaseModel):
    schema_version: Literal["UserSignedUp"] = "UserSignedUp"
    username: str
    password_hash: str


class AccountDeleted(BaseModel):
    schema_version: Literal["AccountDeleted"] = "AccountDeleted"


class UserState(BaseModel):
    schema_version: Literal["UserState"] = "UserState"
    username: str
    password_hash: str
    account_deleted: bool


class User(Aggregate[UserState]):
    @mutator
    def apply_user_signed_up(self, event: UserSignedUp) -> None:
        self._set_state(
            UserState(
                username=event.username,
                password_hash=event.password_hash,
                account_deleted=False,
            )
        )

    @mutator
    def apply_account_deleted(self, _: AccountDeleted) -> None:
        state = self._get_state()
        if state.account_deleted:
            raise ValueError("Account is already deleted.")
        state.account_deleted = True

    def sign_up_with_username(self, username: str, password_hash: str) -> None:
        self._publish(
            UserSignedUp(
                username=username,
                password_hash=password_hash,
            )
        )

    def delete_account(self) -> None:
        state = self._get_state()
        if state.account_deleted:
            raise ValueError("Account is already deleted.")
        self._publish(AccountDeleted())


user = User()

user.sign_up_with_username("user1", "hashed_password")
user.delete_account()

print(user._get_state())