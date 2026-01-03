from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel


class SubscriptionTier(StrEnum):
    FREE = "free"
    PREMIUM = "premium"


class UserRead(BaseModel):
    id: UUID
    created_topics_count: int
    subscription_tier: SubscriptionTier
