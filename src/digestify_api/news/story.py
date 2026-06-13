from datetime import datetime
from typing import Literal, Self
from uuid import UUID, uuid4

from digestify_api.infrastructure.couchdb import Document
from digestify_api.news.topic import Language


class Story(Document):
    type: Literal["story"] = "story"
    topic_id: UUID
    title: str
    body: str
    language: Language
    created_at: datetime

    @classmethod
    def create(
        cls,
        *,
        topic_id: UUID,
        title: str,
        body: str,
        language: Language,
        created_at: datetime,
    ) -> Self:
        return cls(
            id=str(uuid4()),
            topic_id=topic_id,
            title=title,
            body=body,
            language=language,
            created_at=created_at,
        )
