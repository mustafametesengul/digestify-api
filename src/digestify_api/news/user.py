from datetime import UTC, datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field

from rillo import Aggregate


class UserState(BaseModel):
    user_id: UUID


class CreateUser(BaseModel):
    type: Literal["CreateUser"] = "CreateUser"
    user_id: UUID
    created_at: datetime


class UserCreated(BaseModel):
    type: Literal["UserCreated"] = "UserCreated"
    user_id: UUID
    created_at: datetime


class User(Aggregate[UserState, UserCreated, CreateUser]):
    pass
