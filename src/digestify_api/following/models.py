from uuid import UUID

from sqlmodel import Field, SQLModel

from digestify_api.models import Entity

SCHEMA = "following"


class User(Entity, table=True):
    __table_args__ = {"schema": SCHEMA}
    __tablename__ = "users"
    followed_topics_count: int = Field(nullable=False, index=True, default=0)


class Topic(Entity, table=True):
    __table_args__ = {"schema": SCHEMA}
    __tablename__ = "topics"
    user_id: UUID = Field(foreign_key=f"{SCHEMA}.users.id", nullable=False)
    followers_count: int = Field(nullable=False, index=True, default=0)


class Follow(SQLModel, table=True):
    __table_args__ = {"schema": SCHEMA}
    __tablename__ = "follows"
    user_id: UUID = Field(foreign_key=f"{SCHEMA}.users.id", primary_key=True)
    topic_id: UUID = Field(foreign_key=f"{SCHEMA}.topics.id", primary_key=True)
    is_following: bool = Field(nullable=False, default=True, index=True)
