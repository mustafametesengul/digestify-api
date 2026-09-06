from enum import StrEnum
from typing import Literal
from uuid import UUID

from digestify_api.couchdb import Document


class Language(StrEnum):
    EN_US = "en-US"
    TR_TR = "tr-TR"


class Topic(Document):
    type: Literal["topic"]
    user_id: UUID
    name: str
    description: str
    language: Language
    is_deleted: bool
