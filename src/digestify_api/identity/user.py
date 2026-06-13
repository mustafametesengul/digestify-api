from typing import Literal, Self
from uuid import UUID

from digestify_api.infrastructure.couchdb import Document


class User(Document):
    type: Literal["user"] = "user"
    email: str
    is_deleted: bool = False

    @classmethod
    def sign_up(cls, id: UUID, email: str) -> Self:
        return cls(id=str(id), email=email)

    def is_active(self) -> bool:
        return not self.is_deleted

    def delete(self) -> None:
        self.is_deleted = True
