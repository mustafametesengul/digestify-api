from pydantic import BaseModel
from typing import AsyncIterator, Literal
from uuid import UUID

from digestify_api.couchdb import Document, Database


class User(Document):
    type: Literal["user"] = "user"
    email: str
    is_deleted: bool = False


class Change(BaseModel):
    id: UUID
    seq: str
    email: str
    is_deleted: bool


class UserService:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def init(self) -> None:
        await self._database.ensure_database()
        await self._database.ensure_index(
            fields=["email"],
            name="user_email_index",
        )

    async def get(self, user_id: UUID) -> User | None:
        user = await self._database.get(User, str(user_id))
        if user is None or user.is_deleted:
            return None
        return user

    async def create(self, user_id: UUID, email: str) -> User:
        user = User(id=str(user_id), email=email)
        await self._database.save(user)
        return user

    async def delete(self, user_id: UUID) -> bool:
        user = await self._database.get(User, str(user_id))
        if user is None or user.is_deleted:
            return False

        user.is_deleted = True
        await self._database.save(user)
        return True

    async def changes(self, since: str = "0") -> AsyncIterator[Change]:
        async for change in self._database.changes(User, since=since):
            if isinstance(change.doc, User):
                yield Change(
                    id=UUID(change.id),
                    seq=change.seq,
                    email=change.doc.email,
                    is_deleted=change.doc.is_deleted,
                )
