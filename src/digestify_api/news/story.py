from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, Field

from digestify_api.couchdb import Document
from digestify_api.news.topic import Language


class StoryDraft(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=20000)


class Story(StoryDraft):
    id: UUID
    topic_id: UUID
    language: Language
    created_at: AwareDatetime


class StoryBatch(Document):
    type: Literal["story_batch"] = "story_batch"
    user_id: UUID
    topic_id: UUID
    day: date
    stories: list[Story] = Field(max_length=20)
