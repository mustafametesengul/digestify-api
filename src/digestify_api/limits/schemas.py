from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel


class SubscriptionTier(StrEnum):
    FREE = "free"
    PREMIUM = "premium"


class UserRead(BaseModel):
    id: UUID
    subscription_tier: SubscriptionTier
    created_topics_count: int
    followed_topics_count: int
