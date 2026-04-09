from datetime import UTC, datetime

from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field

from digestify_api.news.topic import CreateTopic, ActivateTopic


UserMessage = Annotated[
    CreateTopic | ActivateTopic,
    Field(discriminator="type"),
]


class User(BaseModel):
    type: Literal["User"] = "User"
    id: UUID
    version: int
    pending_actions: list[UserMessage]
    topics_count: int
    active_topics_count: int
    is_deleted: bool
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = None
    outbox: list[UserMessage] = Field(default_factory=list)

    @classmethod
    def create(cls, id: UUID) -> Self:
        return cls(
            id=id,
            topics_count=0,
            active_topics_count=0,
            is_deleted=False,
            pending_actions=[],
            version=1,
        )

    def create_topic(self, command: CreateTopic) -> None:
        if self.is_deleted:
            raise ValueError("User is deleted")

        if len(self.pending_actions) >= 5:
            raise ValueError("User has reached the maximum number of pending actions")

        if self.topics_count >= 10:
            raise ValueError("User has reached the maximum number of topics")

        if self.active_topics_count >= 5:
            raise ValueError("User has reached the maximum number of active topics")

        self.pending_actions.append(command)
        self.topics_count += 1
        self.updated_at = datetime.now(UTC)
        self.outbox.append(command)

    def on_topic_created(self) -> None:
        pass

    def activate_topic(self) -> None:
        pass

    def on_topic_activated(self) -> None:
        pass

    def deactivate_topic(self) -> None:
        pass

    def on_topic_deactivated(self) -> None:
        pass

    def on_topic_deleted(self) -> None:
        pass
