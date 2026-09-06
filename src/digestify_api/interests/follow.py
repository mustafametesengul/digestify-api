from typing import Literal
from uuid import UUID


from digestify_api.couchdb import Document


class Follow(Document):
    type: Literal["follow"] = "follow"
    user_id: UUID
    topic_id: UUID
    is_following: bool
