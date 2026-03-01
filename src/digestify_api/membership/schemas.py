from enum import StrEnum
from uuid import UUID

from digestify_api import infrastructure


class UserTier(StrEnum):
    FREE = "free"
    PREMIUM = "premium"
    ADMIN = "admin"


class UserTierChanged(infrastructure.Event):
    user_id: UUID
    tier: UserTier
    version: int
