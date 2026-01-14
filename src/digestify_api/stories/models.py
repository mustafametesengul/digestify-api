from uuid import UUID

from sqlmodel import Field

from digestify_api.models import Entity

from datetime import datetime

SCHEMA = "stories"


class Topic(Entity, table=True):
    __table_args__ = {"schema": SCHEMA}
    __tablename__ = "topics"
    name: str = Field(nullable=False)
    description: str = Field(nullable=False)
    language: str = Field(nullable=False, index=True)
    image_url: str | None = Field(nullable=True, default=None)
    is_active: bool = Field(nullable=False, default=True, index=True)


class Story(Entity, table=True):
    __table_args__ = {"schema": SCHEMA}
    __tablename__ = "stories"
    topic_id: UUID = Field(
        foreign_key=f"{SCHEMA}.topics.id", nullable=False, index=True
    )
    title: str = Field(nullable=False)
    image_url: str | None = Field(nullable=True, default=None)
    content: str = Field(nullable=False)
    language: str = Field(nullable=False, index=True)
