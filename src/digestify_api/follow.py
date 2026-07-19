from pydantic import BaseModel
from typing import AsyncIterator, Literal
from uuid import UUID

from digestify_api.couchdb import Document, Database


class Follow(Document):
    type: Literal["follow"] = "follow"
    user_id: UUID
    topic_id: UUID
    is_following: bool


class FollowService:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def init(self) -> None:
        await self._database.ensure_database()
        await self._database.ensure_index(
            fields=["is_following"],
            name="follow_is_following_index",
        )

    def _follow_id(self, user_id: UUID, topic_id: UUID) -> str:
        return f"{user_id}_{topic_id}"

    async def follow(self, user_id: UUID, topic_id: UUID) -> None:
        follow = await self._database.get(Follow, self._follow_id(user_id, topic_id))
        if follow is None:
            follow = Follow(
                id=self._follow_id(user_id, topic_id),
                user_id=user_id,
                topic_id=topic_id,
                is_following=True,
            )
        else:
            if follow.is_following:
                return
            follow.is_following = True
        await self._database.save(follow)

    async def unfollow(self, user_id: UUID, topic_id: UUID) -> None:
        follow = await self._database.get(Follow, self._follow_id(user_id, topic_id))
        if follow is None:
            follow = Follow(
                id=self._follow_id(user_id, topic_id),
                user_id=user_id,
                topic_id=topic_id,
                is_following=False,
            )
        else:
            if not follow.is_following:
                return
            follow.is_following = False
        await self._database.save(follow)
