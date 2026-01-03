from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel

SCHEMA = "stories"


class User(SQLModel, table=True):
    __table_args__ = {"schema": SCHEMA}
    __tablename__ = "users"
    id: UUID = Field(primary_key=True, default_factory=uuid4)


class Topic(SQLModel, table=True):
    __table_args__ = {"schema": SCHEMA}
    __tablename__ = "topics"
    id: UUID = Field(primary_key=True, default_factory=uuid4)
    user_id: UUID = Field(foreign_key="users.id", nullable=False, index=True)
    name: str = Field(nullable=False)
    description: str = Field(nullable=False)
    is_public: bool = Field(nullable=False, index=True)
    locale: str = Field(nullable=False, index=True)
    image_url: str | None = Field(nullable=True, default=None)


class Story(SQLModel, table=True):
    __table_args__ = {"schema": SCHEMA}
    __tablename__ = "stories"
    id: UUID = Field(primary_key=True, default_factory=uuid4)
    topic_id: UUID = Field(foreign_key="topics.id", nullable=False, index=True)
    title: str = Field(nullable=False)
    image_url: str | None = Field(nullable=True, default=None)
    content: str = Field(nullable=False)
    locale: str = Field(nullable=False, index=True)
