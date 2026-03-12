from datetime import date, datetime, time
from enum import StrEnum
from uuid import UUID

from asyncpg import Connection
from pydantic import BaseModel, Field, field_validator
from pydantic_extra_types.timezone_name import TimeZoneName


class Schedule(BaseModel):
    schedule_time: time = Field(..., json_schema_extra={"example": "17:04:13"})
    schedule_timezone: TimeZoneName

    @field_validator("schedule_time")
    @classmethod
    def validate_schedule_time_is_naive(cls, schedule_time: time) -> time:
        if schedule_time.tzinfo is not None:
            raise ValueError(
                "schedule_time must not include a UTC offset. "
                "Provide local time and use schedule_timezone for timezone."
            )
        return schedule_time


class Language(StrEnum):
    EN_US = "en-US"
    TR_TR = "tr-TR"


class Topic(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    description: str
    language: Language
    image_url: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime | None
    schedule_time: time
    schedule_timezone: TimeZoneName
    schedule_version: int
    last_execution_date: date | None
    is_deleted: bool


async def create_tables(connection: Connection) -> None:
    await connection.execute(
        """
        CREATE TABLE IF NOT EXISTS topics (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            language TEXT NOT NULL,
            image_url TEXT,
            is_active BOOLEAN NOT NULL,
            is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ,
            schedule_time TIME NOT NULL,
            schedule_timezone TEXT NOT NULL,
            schedule_version INT NOT NULL,
            last_execution_date DATE
        );
        """
    )


async def create_topic(conn: Connection, topic: Topic) -> None:
    await conn.execute(
        """
        INSERT INTO topics
        (id, user_id, is_deleted, name, description, language, image_url,
        is_active, created_at, updated_at, schedule_time,
        schedule_timezone, schedule_version, last_execution_date)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
        """,
        topic.id,
        topic.user_id,
        topic.is_deleted,
        topic.name,
        topic.description,
        topic.language,
        topic.image_url,
        topic.is_active,
        topic.created_at,
        topic.updated_at,
        topic.schedule_time,
        topic.schedule_timezone,
        topic.schedule_version,
        topic.last_execution_date,
    )


async def update_topic(conn: Connection, topic: Topic) -> None:
    await conn.execute(
        """
        UPDATE topics
        SET is_deleted = $2,
            name = $3,
            description = $4,
            language = $5,
            image_url = $6,
            is_active = $7,
            created_at = $8,
            updated_at = $9,
            schedule_time = $10,
            schedule_timezone = $11,
            schedule_version = $12,
            last_execution_date = $13
        WHERE id = $1
        """,
        topic.id,
        topic.is_deleted,
        topic.name,
        topic.description,
        topic.language,
        topic.image_url,
        topic.is_active,
        topic.created_at,
        topic.updated_at,
        topic.schedule_time,
        topic.schedule_timezone,
        topic.schedule_version,
        topic.last_execution_date,
    )


async def get_topic(
    conn: Connection, topic_id: UUID, lock: bool = False
) -> Topic | None:
    query = "SELECT * FROM topics WHERE id = $1"
    if lock:
        query += " FOR UPDATE"

    row = await conn.fetchrow(query, topic_id)

    if row is None:
        return None

    topic = Topic.model_validate(dict(row))
    return topic
