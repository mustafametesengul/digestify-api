from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from digestify_api.couchdb import Database, Document
from digestify_api.topic import Language


class Topic(BaseModel):
    topic_id: UUID
    user_id: UUID
    name: str
    description: str
    language: Language
    is_deleted: bool
    rev: str


class TopicView(Document):
    type: Literal["topic_view"] = "topic_view"
    topic: Topic | None = None
    follower_count: int | None = None
    processed_events: list[str]


class TopicViewService:
    def __init__(
        self,
        database: Database,
    ) -> None:
        self._database = database

    async def init(self) -> None:
        await self._database.ensure_database()
        await self._database.ensure_index(
            fields=["user_id"],
            name="topic_user_id_index",
        )

    async def on_topic_update(
        self,
        topic_id: UUID,
        user_id: UUID,
        name: str,
        description: str,
        language: Language,
        is_deleted: bool,
        rev: str,
    ) -> None:
        topic_view = await self._database.get(TopicView, str(topic_id))
        if topic_view is None:
            topic_view = TopicView(
                id=str(topic_id),
                topic=Topic(
                    topic_id=topic_id,
                    user_id=user_id,
                    name=name,
                    description=description,
                    language=language,
                    is_deleted=is_deleted,
                    rev=rev,
                ),
                processed_events=[],
            )
        else:
            if topic_view.topic is not None and topic_view.topic.rev >= rev:
                return
            topic_view.topic = Topic(
                topic_id=topic_id,
                user_id=user_id,
                name=name,
                description=description,
                language=language,
                is_deleted=is_deleted,
                rev=rev,
            )
        await self._database.save(topic_view)

    async def on_follow_update(
        self,
        topic_id: UUID,
        is_following: bool,
        event_id: str,
    ) -> None:
        topic_view = await self._database.get(TopicView, str(topic_id))
        if topic_view is None:
            topic_view = TopicView(
                id=str(topic_id),
                topic=None,
                processed_events=[],
            )
        if event_id in topic_view.processed_events:
            return

        if topic_view.follower_count is None:
            topic_view.follower_count = 0

        if is_following:
            topic_view.follower_count += 1
        else:
            topic_view.follower_count -= 1

        topic_view.processed_events.append(event_id)

        topic_view.processed_events = topic_view.processed_events[-100:]

        await self._database.save(topic_view)
