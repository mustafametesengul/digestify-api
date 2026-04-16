from typing import Literal
from pydantic import BaseModel

from digestify_api.infrastructure import Aggregate, NATSRepository
from nats.js.client import JetStreamContext


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
    def __init__(self, id: str) -> None:
        super().__init__(id)
        self._add_mutator(UserSignedUp, self.apply_user_signed_up)
        self._add_mutator(AccountDeleted, self.apply_account_deleted)

    def apply_user_signed_up(self, event: UserSignedUp) -> None:
        if self._state is not None:
            raise ValueError("User already exists.")
        self._set_state(
            UserState(
                username=event.username,
                password_hash=event.password_hash,
                account_deleted=False,
            )
        )

    def apply_account_deleted(self, _: AccountDeleted) -> None:
        state = self._get_state()
        if state is None:
            raise ValueError("User does not exist.")
        if state.account_deleted:
            raise ValueError("Account is already deleted.")
        state.account_deleted = True
        self._set_state(state)

    def sign_up_with_username(self, username: str, password_hash: str) -> None:
        self._publish(
            UserSignedUp(
                username=username,
                password_hash=password_hash,
            )
        )

    def delete_account(self) -> None:
        state = self._get_state()
        if state is None:
            raise ValueError("User does not exist.")
        if state.account_deleted:
            raise ValueError("Account is already deleted.")
        self._publish(AccountDeleted())


class UserRepository(NATSRepository[User]):
    def __init__(self, js: JetStreamContext) -> None:
        super().__init__(js, subject_prefix="user")


user = User(id="user-123")
user.sign_up_with_username("john_doe", "hashed_password")
user.delete_account()
print(user._pending_events)
print(user._get_state())
