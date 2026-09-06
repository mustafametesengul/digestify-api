from datetime import datetime
from typing import Literal
from uuid import UUID

from digestify_api.couchdb import Document
from digestify_api.topics.topic import Language


class Story(Document):
    type: Literal["story"] = "story"
    topic_id: UUID
    title: str
    body: str
    language: Language
    created_at: datetime
