from uuid import UUID

from sqlmodel import Field

from digestify_api.billing.schemas import SubscriptionTier
from digestify_api.models import Entity

SCHEMA = "billing"


class User(Entity, table=True):
    __table_args__ = {"schema": SCHEMA}
    __tablename__ = "users"
    created_topics_count: int = Field(nullable=False, index=True, default=0)
    subscription_tier: SubscriptionTier = Field(
        nullable=False,
        index=True,
        default=SubscriptionTier.FREE,
    )
    discarded: bool = Field(nullable=False, index=True, default=False)


class Topic(Entity, table=True):
    __table_args__ = {"schema": SCHEMA}
    __tablename__ = "topics"
    user_id: UUID = Field(foreign_key=f"{SCHEMA}.users.id", primary_key=True)
