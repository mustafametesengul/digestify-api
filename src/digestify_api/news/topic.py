from datetime import date, datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from digestify_api.couchdb import Document
from digestify_api.tasks.task import DailySchedule


class Language(StrEnum):
    EN_US = "en-US"
    TR_TR = "tr-TR"


class TopicDetails(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=4000)
    language: Language
    schedule: DailySchedule


class Topic(TopicDetails):
    id: UUID
    user_id: UUID
    next_run_at: AwareDatetime
    created_at: AwareDatetime
    updated_at: AwareDatetime


class TopicSlot(BaseModel):
    topic: Topic | None = None
    used_on: date | None = None


class TopicAccount(Document):
    type: Literal["topic_account"] = "topic_account"
    user_id: UUID
    slots: list[TopicSlot] = Field(
        default_factory=lambda: [TopicSlot() for _ in range(5)],
        min_length=5,
        max_length=5,
    )

    def topics(self) -> list[Topic]:
        return [slot.topic for slot in self.slots if slot.topic is not None]

    def due(self, now: datetime) -> list[Topic]:
        return [topic for topic in self.topics() if topic.next_run_at <= now]
