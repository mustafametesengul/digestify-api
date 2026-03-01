from datetime import date, datetime, time
from uuid import UUID

from asyncpg import Connection
from pydantic import BaseModel
from pydantic_extra_types.timezone_name import TimeZoneName

from digestify_api.topics import schemas


class User(BaseModel):
    id: UUID
    created_topics_count: int
    identity_version: int
    membership_version: int
    tier: str
    is_deleted: bool
    created_at: datetime
    updated_at: datetime | None


class Topic(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    description: str
    language: schemas.Language
    image_url: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime | None
    schedule_time: time
    schedule_timezone: TimeZoneName
    schedule_version: int
    last_execution_date: date
    is_deleted: bool


class Story(BaseModel):
    id: UUID
    topic_id: UUID
    title: str
    image_url: str | None
    content: str
    language: schemas.Language
    created_at: datetime
    updated_at: datetime | None
    is_deleted: bool


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


async def create_story(conn: Connection, story: Story) -> None:
    await conn.execute(
        """
        INSERT INTO stories
        (id, is_deleted, created_at, updated_at, topic_id,
        title, image_url, content, language)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        """,
        story.id,
        story.is_deleted,
        story.created_at,
        story.updated_at,
        story.topic_id,
        story.title,
        story.image_url,
        story.content,
        story.language,
    )


async def get_story(
    conn: Connection,
    story_id: UUID,
    lock: bool = False,
) -> Story | None:
    query = "SELECT * FROM stories WHERE id = $1"
    if lock:
        query += " FOR UPDATE"

    row = await conn.fetchrow(query, story_id)
    if row is None:
        return None

    return Story.model_validate(dict(row))


async def create_user(conn: Connection, user: User) -> None:
    await conn.execute(
        """
        INSERT INTO users
        (id, created_topics_count, created_at, updated_at)
        VALUES ($1, $2, $3, $4)
        """,
        user.id,
        user.created_topics_count,
        user.created_at,
        user.updated_at,
    )


async def update_user(conn: Connection, user: User) -> None:
    await conn.execute(
        """
        UPDATE users
        SET created_topics_count = $2,
            created_at = $3,
            updated_at = $4
        WHERE id = $1
        """,
        user.id,
        user.created_topics_count,
        user.created_at,
        user.updated_at,
    )


async def get_user(conn: Connection, user_id: UUID, lock: bool = False) -> User | None:
    query = "SELECT * FROM users WHERE id = $1"
    if lock:
        query += " FOR UPDATE"

    row = await conn.fetchrow(query, user_id)

    if row is None:
        return None

    user = User.model_validate(dict(row))
    return user
