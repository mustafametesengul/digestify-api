from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class Follow(BaseModel):
    user_id: UUID
    topic_id: UUID
    is_following: bool
    created_at: datetime
    updated_at: datetime | None
