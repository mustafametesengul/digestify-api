from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


class TokenPayload(BaseModel):
    id: UUID
    is_anonymous: bool


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["Bearer"] = "Bearer"
