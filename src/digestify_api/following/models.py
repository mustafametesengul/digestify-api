from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel

SCHEMA = "following"


class User(SQLModel, table=True):
    __table_args__ = {"schema": SCHEMA}
    __tablename__ = "users"
    id: UUID = Field(primary_key=True, default_factory=uuid4)
    followed_topics_count: int = Field(nullable=False, index=True, default=0)


class Topic(SQLModel, table=True):
    __table_args__ = {"schema": SCHEMA}
    __tablename__ = "topics"
    id: UUID = Field(primary_key=True, default_factory=uuid4)
    user_id: UUID = Field(foreign_key="users.id", nullable=False, ondelete="CASCADE")
    followers_count: int = Field(nullable=False, index=True, default=0)


class Follow(SQLModel, table=True):
    __table_args__ = {"schema": SCHEMA}
    __tablename__ = "follows"
    user_id: UUID = Field(foreign_key="users.id", primary_key=True, ondelete="CASCADE")
    topic_id: UUID = Field(
        foreign_key="topics.id", primary_key=True, ondelete="CASCADE"
    )
    is_following: bool = Field(nullable=False, default=True, index=True)
