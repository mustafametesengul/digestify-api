from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel


class SubscriptionTier(StrEnum):
    FREE = "free"
    PREMIUM = "premium"


class User(BaseModel):
    id: UUID
    discarded: bool
    subscription_tier: SubscriptionTier
    created_topics_count: int
    followed_topics_count: int
    created_at: datetime
    updated_at: datetime | None
