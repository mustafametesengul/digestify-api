from uuid import UUID

from pydantic import BaseModel


class StoryTaskPayload(BaseModel):
    topic_id: UUID
