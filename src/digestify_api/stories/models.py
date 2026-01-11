from uuid import UUID

from sqlmodel import Field

from digestify_api.models import Entity

SCHEMA = "stories"


class User(Entity, table=True):
    __table_args__ = {"schema": SCHEMA}
    __tablename__ = "users"


class Topic(Entity, table=True):
    __table_args__ = {"schema": SCHEMA}
    __tablename__ = "topics"
    user_id: UUID = Field(foreign_key="users.id", nullable=False, index=True)
    name: str = Field(nullable=False)
    description: str = Field(nullable=False)
    is_public: bool = Field(nullable=False, index=True)
    locale: str = Field(nullable=False, index=True)
    image_url: str | None = Field(nullable=True, default=None)


class Story(Entity, table=True):
    __table_args__ = {"schema": SCHEMA}
    __tablename__ = "stories"
    topic_id: UUID = Field(foreign_key="topics.id", nullable=False, index=True)
    title: str = Field(nullable=False)
    image_url: str | None = Field(nullable=True, default=None)
    content: str = Field(nullable=False)
    locale: str = Field(nullable=False, index=True)
