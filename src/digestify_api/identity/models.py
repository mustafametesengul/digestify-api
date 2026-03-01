from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class User(BaseModel):
    id: UUID
    username: str | None
    password_hash: str | None
    created_at: datetime
    updated_at: datetime | None
    version: int
    is_deleted: bool
