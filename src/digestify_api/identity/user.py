from typing import Annotated, Literal, override
from uuid import UUID

from pydantic import BaseModel, Field
from rillo import Aggregate


class State(BaseModel):
    email: str
    is_deleted: bool


class UserSignedUp(BaseModel):
    type: Literal["UserSignedUpV1"] = "UserSignedUpV1"
    email: str


class AccountDeleted(BaseModel):
    type: Literal["AccountDeletedV1"] = "AccountDeletedV1"


type Event = Annotated[UserSignedUp | AccountDeleted, Field(discriminator="type")]


class User(Aggregate[State, Event]):
    def __init__(self, id: UUID) -> None:
        super().__init__(str(id))

    def sign_up(self, email: str) -> None:
        if self._state is not None:
            raise ValueError("User already exists")
        self._emit(UserSignedUp(email=email))

    def delete_account(self) -> None:
        if self._state is None or self._state.is_deleted:
            raise ValueError("User does not exist or is already deleted")
        self._emit(AccountDeleted())

    @override
    def apply(self, event: Event) -> None:
        match event:
            case UserSignedUp():
                self._state = State(
                    email=event.email,
                    is_deleted=False,
                )
            case AccountDeleted():
                if self._state is not None:
                    self._state.is_deleted = True

    def is_active(self) -> bool:
        return self._state is not None and not self._state.is_deleted

    def email(self) -> str:
        if self._state is None or self._state.is_deleted:
            raise ValueError("User does not exist or is deleted")
        return self._state.email
