from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field
from rillo import Aggregate


class State(BaseModel):
    is_deleted: bool


class UserDeleted(BaseModel):
    type: Literal["UserDeleted"] = "UserDeleted"
    created_at: datetime


class UserCreated(BaseModel):
    type: Literal["UserCreated"] = "UserCreated"
    created_at: datetime


type Event = Annotated[UserCreated | UserDeleted, Field(discriminator="type")]


class User(Aggregate[State, Event]):
    def create(self, created_at: datetime) -> None:
        self._emit(UserCreated(created_at=created_at))

    def apply(self, event: Event) -> None:
        match event:
            case UserCreated():
                self._state = State(is_deleted=False)
            case UserDeleted():
                if self._state is not None:
                    self._state.is_deleted = True
