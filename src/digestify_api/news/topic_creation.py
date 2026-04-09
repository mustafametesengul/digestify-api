from datetime import UTC, datetime
from typing import Annotated, Literal, Self
from uuid import UUID, uuid7

from pydantic import BaseModel, Field

from digestify_api.news.topic import Language, Schedule, CreateTopic
from digestify_api.news.user import ReserveTopic, TopicReserved, TopicNotReserved


TopicMessage = Annotated[
    CreateTopic | ReserveTopic,
    Field(discriminator="type"),
]


class CreateTopicSaga(BaseModel):
    type: Literal["CreateTopicSaga"] = "CreateTopicSaga"
    id: UUID
    topic_id: UUID
    user_id: UUID
    name: str
    description: str
    language: Language
    created_at: datetime
    schedule: Schedule
    outbox: list[TopicMessage]
    is_completed: bool

    @classmethod
    def start(
        cls,
        user_id: UUID,
        name: str,
        description: str,
        language: Language,
        schedule: Schedule,
    ) -> Self:
        id = uuid7()
        topic_id = uuid7()
        topic = cls(
            id=id,
            topic_id=topic_id,
            user_id=user_id,
            name=name,
            description=description,
            language=language,
            created_at=datetime.now(UTC),
            schedule=schedule,
            is_completed=False,
            outbox=[ReserveTopic(id=id, topic_id=topic_id, user_id=user_id)],
        )
        return topic

    def topic_reserved(self, event: TopicReserved) -> None:
        self.outbox.append(
            CreateTopic(
                topic_id=event.id,
                topic_id=self.topic_id,
                user_id=self.user_id,
                name=self.name,
                description=self.description,
                language=self.language,
                schedule=self.schedule,
            )
        )
        self.is_completed = True

    def topic_not_reserved(self, _: TopicNotReserved) -> None:
        self.is_completed = True
