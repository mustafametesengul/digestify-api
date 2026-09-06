from typing import Literal, Self
from uuid import UUID, uuid4

from digestify_api.couchdb import Document


class User(Document):
    """An account holder.

    Users are soft-deleted via `is_deleted` rather than removed, so the
    `_changes` feed can surface the deletion to downstream consumers.
    """

    type: Literal["user"] = "user"
    email: str
    token_generation: UUID
    is_deleted: bool = False

    @classmethod
    def create(cls, user_id: UUID, email: str) -> Self:
        return cls(id=str(user_id), email=email, token_generation=uuid4())

    def revoke_tokens(self) -> None:
        """Invalidate tokens carrying the previous account generation."""
        self.token_generation = uuid4()

    def delete(self) -> None:
        self.is_deleted = True
