from datetime import UTC, datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field

from rillo import Aggregate


class UserState(BaseModel):
    is_deleted: bool


class UserDeleted(BaseModel):
    type: Literal["UserDeleted"] = "UserDeleted"
    created_at: datetime


class UserCreated(BaseModel):
    type: Literal["UserCreated"] = "UserCreated"
    created_at: datetime


class User(Aggregate[UserState]):
    def create(self, created_at: datetime) -> None:
        self._emit(
            UserCreated(
                created_at=created_at,
            )
        )

    def apply(self, event: UserCreated | UserDeleted) -> UserState:
        state = self._state
        match event:
            case UserCreated():
                return UserState(
                    is_deleted=False,
                )
            case UserDeleted():
                return UserState(
                    is_deleted=True,
                )
