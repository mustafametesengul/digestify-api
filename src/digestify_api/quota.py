from datetime import datetime
from datetime import time as time_
from uuid import UUID, uuid4
from typing import Literal
from digestify_api.couchdb import Document, Database
from pydantic import BaseModel, Field, field_validator
from pydantic_extra_types.timezone_name import TimeZoneName


class Schedule(BaseModel):
    time: time_ = Field(..., json_schema_extra={"example": "17:04:13"})
    timezone: TimeZoneName

    @field_validator("time")
    @classmethod
    def validate_schedule_time_is_naive(cls, time: time_) -> time_:
        if time.tzinfo is not None:
            raise ValueError(
                "Schedule time must not include a UTC offset. "
                "Provide local time and use schedule_timezone for timezone."
            )
        return time


class Fetch(BaseModel):
    topic_id: UUID
    story_ids: list[UUID]
    fetched_at: datetime


class Quota(Document):
    type: Literal["quota"]
    user_id: UUID
    fetch_history: list[Fetch]
    active_topics: list[UUID]


class QuotaService:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def init(self) -> None:
        await self._database.ensure_database()
        await self._database.ensure_index(
            fields=["user_id"],
            name="quota_user_id_index",
        )

    async def create(self, user_id: UUID) -> None:
        quota = Quota(
            type="quota",
            id=str(uuid4()),
            user_id=user_id,
            fetch_history=[],
            active_topics=[],
        )
        await self._database.save(quota)

    async def activate_topic(self, user_id: UUID, topic_id: UUID) -> None:
        quota = await self._database.get(Quota, str(user_id))
        if quota is None:
            raise ValueError(f"Quota for user {user_id} not found.")
        if topic_id not in quota.active_topics:
            quota.active_topics.append(topic_id)
            await self._database.save(quota)

    async def deactivate_topic(self, user_id: UUID, topic_id: UUID) -> None:
        quota = await self._database.get(Quota, str(user_id))
        if quota is None:
            raise ValueError(f"Quota for user {user_id} not found.")
        if topic_id in quota.active_topics:
            quota.active_topics.remove(topic_id)
            await self._database.save(quota)
