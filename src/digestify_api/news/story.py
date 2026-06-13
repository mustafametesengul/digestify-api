from datetime import date
from typing import Literal
from uuid import UUID

from digestify_api.infrastructure.couchdb import Document
from digestify_api.news.topic import Language


class Story(Document):
    type: Literal["story"] = "story"
    topic_id: UUID
    title: str
    body: str
    language: Language
    created_at: date
