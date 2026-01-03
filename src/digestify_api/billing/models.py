from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel

from digestify_api.billing.schemas import SubscriptionTier

SCHEMA = "billing"


class User(SQLModel, table=True):
    __table_args__ = {"schema": SCHEMA}
    __tablename__ = "users"
    id: UUID = Field(primary_key=True, default_factory=uuid4)
    created_topics_count: int = Field(nullable=False, index=True, default=0)
    subscription_tier: SubscriptionTier = Field(
        nullable=False,
        index=True,
        default=SubscriptionTier.FREE,
    )


class Topic(SQLModel, table=True):
    __table_args__ = {"schema": SCHEMA}
    __tablename__ = "topics"
    id: UUID = Field(primary_key=True)
    user_id: UUID = Field(
        foreign_key="billing.users.id",
        primary_key=True,
        ondelete="CASCADE",
    )
