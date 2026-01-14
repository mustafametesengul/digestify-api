from sqlmodel import Field

from digestify_api.limits.schemas import SubscriptionTier
from digestify_api.models import Entity

SCHEMA = "limits"


class User(Entity, table=True):
    __table_args__ = {"schema": SCHEMA}
    __tablename__ = "users"
    subscription_tier: SubscriptionTier = Field(
        nullable=False,
        index=True,
        default=SubscriptionTier.FREE,
    )
    created_topics_count: int = Field(nullable=False, index=True, default=0)
    followed_topics_count: int = Field(nullable=False, index=True, default=0)
