from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from pydantic_extra_types.timezone_name import TimeZoneName

from digestify_api import dependencies, models, queries, routers
from digestify_api.routers import topics as topics_router


def _embedding(value: float) -> str:
    return "[" + ",".join([f"{value:.6f}"] * 1536) + "]"


class FakeOpenAI:
    def __init__(self) -> None:
        self.embedding = _embedding(0.123456)
        self.flagged = False

    async def check_for_moderation(self, texts: list[str]) -> list[bool]:
        return [self.flagged for _ in texts]

    async def get_embeddings(self, texts: list[str]) -> list[str]:
        return [self.embedding for _ in texts]


async def _create_user(
    db: dependencies.db.DBManager,
    user_id: UUID,
    now: datetime,
    tier: models.users.UserTier,
    created_topics_count: int = 0,
    active_topics_count: int = 0,
) -> None:
    user = models.users.User(
        id=user_id,
        username=f"user_{user_id.hex[:8]}",
        password_hash="hashed",
        discarded=False,
        tier=tier,
        active_topics_count=active_topics_count,
        created_topics_count=created_topics_count,
        followed_topics_count=0,
        created_at=now,
        updated_at=None,
        tier_last_confirmed_at=now,
    )
    async with db.get_connection() as connection:
        await queries.users.create(connection, user)


async def _create_topic(
    db: dependencies.db.DBManager,
    topic_id: UUID,
    user_id: UUID,
    now: datetime,
    followers_count: int = 1,
    is_active: bool = True,
    language: models.topics.Language = models.topics.Language.EN_US,
    schedule_time: time = time(11, 0),
    schedule_timezone: str = "UTC",
    schedule_version: int = 1,
    schedule_date: date | None = None,
    embedding: str | None = None,
) -> None:
    topic = models.topics.Topic(
        id=topic_id,
        user_id=user_id,
        discarded=False,
        image_url=None,
        is_active=is_active,
        name=f"topic_{topic_id.hex[:8]}",
        description="description",
        language=language,
        followers_count=followers_count,
        created_at=now,
        updated_at=None,
        embedding=embedding or _embedding(0.123456),
        schedule_time=schedule_time,
        schedule_timezone=TimeZoneName(schedule_timezone),
        schedule_version=schedule_version,
        schedule_date=schedule_date or now.date(),
    )
    async with db.get_connection() as connection:
        await queries.topics.create(connection, topic)


@pytest.fixture
def app(
    db: dependencies.db.DBManager,
    auth_manager: dependencies.auth.AuthManager,
) -> FastAPI:
    app = FastAPI()
    app.include_router(routers.topics.router)

    app.dependency_overrides[dependencies.db.get_db_manager] = lambda: db
    app.dependency_overrides[dependencies.auth.get_auth_manager] = lambda: auth_manager
    return app


@pytest.fixture
def auth_state(app: FastAPI) -> dict[str, models.auth.Auth]:
    state = {"value": models.auth.Auth(id=uuid4(), is_anonymous=False)}
    app.dependency_overrides[dependencies.auth.get_auth] = lambda: state["value"]
    return state


@pytest.fixture
def fake_openai(monkeypatch: pytest.MonkeyPatch) -> FakeOpenAI:
    fake = FakeOpenAI()
    monkeypatch.setattr(dependencies.openai, "get_openai", lambda: fake)
    return fake


@pytest.fixture
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> datetime:
    now = datetime(2026, 1, 10, 12, 0, tzinfo=timezone.utc)

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return now
            return now.astimezone(tz)

    monkeypatch.setattr(topics_router, "datetime", FixedDateTime)
    return now


async def test_create_topic_success_creates_follow_and_task(
    client: AsyncClient,
    db: dependencies.db.DBManager,
    auth_state: dict[str, models.auth.Auth],
    fake_openai: FakeOpenAI,
    fixed_now: datetime,
) -> None:
    user_id = uuid4()
    auth_state["value"] = models.auth.Auth(id=user_id, is_anonymous=False)
    await _create_user(db, user_id, fixed_now, tier=models.users.UserTier.PREMIUM)

    response = await client.post(
        "/topics/create",
        json={
            "name": "AIX",
            "description": "AI updates",
            "language": "en-US",
            "schedule_time": "11:00:00",
            "schedule_timezone": "UTC",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["user_id"] == str(user_id)
    assert body["schedule_date"] == "2026-01-11"

    topic_id = UUID(body["id"])
    async with db.get_connection() as connection:
        user = await queries.users.get(connection, user_id)
        assert user is not None
        assert user.created_topics_count == 1
        assert user.active_topics_count == 1

        follow = await queries.follows.get(connection, user_id, topic_id)
        assert follow is not None
        assert follow.is_following is True

        topic = await queries.topics.get(connection, topic_id)
        assert topic is not None
        assert topic.embedding == fake_openai.embedding

        task_row = await connection.fetchrow(
            "SELECT name, status, scheduled_at FROM tasks WHERE payload::json->>'topic_id' = $1",
            str(topic_id),
        )
        assert task_row is not None
        assert task_row["name"] == "fetch_and_save_stories"
        assert task_row["status"] == "pending"
        assert task_row["scheduled_at"] == fixed_now + timedelta(hours=22, minutes=50)


async def test_create_topic_clamps_task_schedule_when_within_10_minutes(
    client: AsyncClient,
    db: dependencies.db.DBManager,
    auth_state: dict[str, models.auth.Auth],
    fake_openai: FakeOpenAI,
    fixed_now: datetime,
) -> None:
    user_id = uuid4()
    auth_state["value"] = models.auth.Auth(id=user_id, is_anonymous=False)
    await _create_user(db, user_id, fixed_now, tier=models.users.UserTier.PREMIUM)

    response = await client.post(
        "/topics/create",
        json={
            "name": "AIX",
            "description": "AI updates",
            "language": "en-US",
            "schedule_time": "12:05:00",
            "schedule_timezone": "UTC",
        },
    )
    assert response.status_code == 201

    topic_id = UUID(response.json()["id"])
    async with db.get_connection() as connection:
        task_row = await connection.fetchrow(
            "SELECT scheduled_at FROM tasks WHERE payload::json->>'topic_id' = $1 ORDER BY created_at DESC LIMIT 1",
            str(topic_id),
        )
        assert task_row is not None
        assert task_row["scheduled_at"] == fixed_now


async def test_create_topic_rejects_anonymous_user(
    client: AsyncClient,
    auth_state: dict[str, models.auth.Auth],
    fake_openai: FakeOpenAI,
) -> None:
    auth_state["value"] = models.auth.Auth(id=uuid4(), is_anonymous=True)

    response = await client.post(
        "/topics/create",
        json={
            "name": "AIX",
            "description": "AI updates",
            "language": "en-US",
            "schedule_time": "11:00:00",
            "schedule_timezone": "UTC",
        },
    )
    assert response.status_code == 403


async def test_create_topic_rejects_offset_aware_schedule_time(
    client: AsyncClient,
    auth_state: dict[str, models.auth.Auth],
) -> None:
    auth_state["value"] = models.auth.Auth(id=uuid4(), is_anonymous=False)

    response = await client.post(
        "/topics/create",
        json={
            "name": "AIX",
            "description": "AI updates",
            "language": "en-US",
            "schedule_time": "11:00:00+03:00",
            "schedule_timezone": "UTC",
        },
    )

    assert response.status_code == 422


async def test_change_schedule_updates_topic_and_creates_task(
    client: AsyncClient,
    db: dependencies.db.DBManager,
    auth_state: dict[str, models.auth.Auth],
    fixed_now: datetime,
) -> None:
    user_id = uuid4()
    topic_id = uuid4()
    auth_state["value"] = models.auth.Auth(id=user_id, is_anonymous=False)

    await _create_user(db, user_id, fixed_now, tier=models.users.UserTier.PREMIUM)
    await _create_topic(
        db,
        topic_id=topic_id,
        user_id=user_id,
        now=fixed_now,
        schedule_time=time(13, 0),
        schedule_date=fixed_now.date(),
    )

    response = await client.post(
        "/topics/change_schedule",
        json={
            "topic_id": str(topic_id),
            "schedule_time": "08:00:00",
            "schedule_timezone": "UTC",
        },
    )
    assert response.status_code == 200

    async with db.get_connection() as connection:
        topic = await queries.topics.get(connection, topic_id)
        assert topic is not None
        assert topic.schedule_version == 2
        assert topic.schedule_time == time(8, 0)
        assert topic.schedule_date == date(2026, 1, 11)

        task_row = await connection.fetchrow(
            "SELECT scheduled_at FROM tasks WHERE payload::json->>'topic_id' = $1 ORDER BY created_at DESC LIMIT 1",
            str(topic_id),
        )
        assert task_row is not None
        assert task_row["scheduled_at"] == datetime(
            2026, 1, 11, 7, 50, tzinfo=timezone.utc
        )


async def test_get_most_followed_returns_sorted_topics(
    client: AsyncClient,
    db: dependencies.db.DBManager,
    auth_state: dict[str, models.auth.Auth],
    fixed_now: datetime,
) -> None:
    user_id = uuid4()
    auth_state["value"] = models.auth.Auth(id=user_id, is_anonymous=False)
    await _create_user(db, user_id, fixed_now, tier=models.users.UserTier.PREMIUM)

    topic_id_low = uuid4()
    topic_id_high = uuid4()
    await _create_topic(
        db,
        topic_id=topic_id_low,
        user_id=user_id,
        now=fixed_now,
        followers_count=2,
    )
    await _create_topic(
        db,
        topic_id=topic_id_high,
        user_id=user_id,
        now=fixed_now,
        followers_count=10,
    )

    response = await client.get("/topics/most_followed", params={"language": "en-US"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2
    assert data[0]["id"] == str(topic_id_high)
    assert data[1]["id"] == str(topic_id_low)


async def test_search_returns_topics_by_embedding(
    client: AsyncClient,
    db: dependencies.db.DBManager,
    auth_state: dict[str, models.auth.Auth],
    fake_openai: FakeOpenAI,
    fixed_now: datetime,
) -> None:
    user_id = uuid4()
    topic_id = uuid4()
    auth_state["value"] = models.auth.Auth(id=user_id, is_anonymous=False)
    fake_openai.embedding = _embedding(0.777777)
    await _create_user(db, user_id, fixed_now, tier=models.users.UserTier.PREMIUM)
    await _create_topic(
        db,
        topic_id=topic_id,
        user_id=user_id,
        now=fixed_now,
        embedding=fake_openai.embedding,
    )

    response = await client.get(
        "/topics/search",
        params={"query": "artificial intelligence", "language": "en-US"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(topic["id"] == str(topic_id) for topic in data)


async def test_activate_topic_marks_active_and_creates_task(
    client: AsyncClient,
    db: dependencies.db.DBManager,
    auth_state: dict[str, models.auth.Auth],
    fixed_now: datetime,
) -> None:
    user_id = uuid4()
    topic_id = uuid4()
    auth_state["value"] = models.auth.Auth(id=user_id, is_anonymous=False)
    await _create_user(
        db,
        user_id,
        fixed_now,
        tier=models.users.UserTier.PREMIUM,
        active_topics_count=0,
    )
    await _create_topic(
        db,
        topic_id=topic_id,
        user_id=user_id,
        now=fixed_now,
        is_active=False,
        schedule_time=time(11, 0),
    )

    response = await client.post("/topics/activate", params={"topic_id": str(topic_id)})
    assert response.status_code == 200

    async with db.get_connection() as connection:
        topic = await queries.topics.get(connection, topic_id)
        assert topic is not None
        assert topic.is_active is True
        assert topic.schedule_version == 2
        assert topic.schedule_date == date(2026, 1, 11)

        user = await queries.users.get(connection, user_id)
        assert user is not None
        assert user.active_topics_count == 1

        task_row = await connection.fetchrow(
            "SELECT name FROM tasks WHERE payload::json->>'topic_id' = $1 ORDER BY created_at DESC LIMIT 1",
            str(topic_id),
        )
        assert task_row is not None
        assert task_row["name"] == "fetch_and_save_stories"


async def test_activate_topic_rejects_free_tier_user(
    client: AsyncClient,
    db: dependencies.db.DBManager,
    auth_state: dict[str, models.auth.Auth],
    fixed_now: datetime,
) -> None:
    user_id = uuid4()
    topic_id = uuid4()
    auth_state["value"] = models.auth.Auth(id=user_id, is_anonymous=False)

    await _create_user(db, user_id, fixed_now, tier=models.users.UserTier.FREE)
    await _create_topic(
        db,
        topic_id=topic_id,
        user_id=user_id,
        now=fixed_now,
        is_active=False,
    )

    response = await client.post("/topics/activate", params={"topic_id": str(topic_id)})
    assert response.status_code == 403

    async with db.get_connection() as connection:
        topic = await queries.topics.get(connection, topic_id)
        assert topic is not None
        assert topic.is_active is False


async def test_deactivate_topic_marks_inactive_and_decrements_counter(
    client: AsyncClient,
    db: dependencies.db.DBManager,
    auth_state: dict[str, models.auth.Auth],
    fixed_now: datetime,
) -> None:
    user_id = uuid4()
    topic_id = uuid4()
    auth_state["value"] = models.auth.Auth(id=user_id, is_anonymous=False)
    await _create_user(
        db,
        user_id,
        fixed_now,
        tier=models.users.UserTier.PREMIUM,
        active_topics_count=1,
    )
    await _create_topic(
        db,
        topic_id=topic_id,
        user_id=user_id,
        now=fixed_now,
        is_active=True,
    )

    response = await client.post(
        "/topics/deactivate",
        params={"topic_id": str(topic_id)},
    )
    assert response.status_code == 200

    async with db.get_connection() as connection:
        topic = await queries.topics.get(connection, topic_id)
        assert topic is not None
        assert topic.is_active is False

        user = await queries.users.get(connection, user_id)
        assert user is not None
        assert user.active_topics_count == 0
