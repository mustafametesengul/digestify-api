from typing import Literal, Self
from uuid import UUID

from digestify_api.couchdb import Document


class User(Document):
    """An account holder.

    Users are soft-deleted via `is_deleted` rather than removed, so the
    `_changes` feed can surface the deletion to downstream consumers.
    """

    type: Literal["user"] = "user"
    email: str
    is_deleted: bool = False

    @classmethod
    def create(cls, user_id: UUID, email: str) -> Self:
        return cls(id=str(user_id), email=email)

    def delete(self) -> None:
        self.is_deleted = True
