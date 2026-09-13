import asyncio
from datetime import timedelta
from uuid import UUID, uuid4

import httpx
import pytest

from digestify_api.app import Settings, create_app
from digestify_api.couchdb import (
    Client,
    Database,
    Repository,
    UnresolvedDocumentConflict,
)
from digestify_api.identity.token import UserClaims, UserRole
from digestify_api.identity.user import User
from digestify_api.news.service import TASK_KIND, Service, TopicLimitReached
from digestify_api.tasks import Partition, Worker
from digestify_api.tasks import Service as TaskService
from tests.couchdb.test_integration import client as client
from tests.couchdb.test_integration import pytestmark as pytestmark
from tests.couchdb.test_integration import service_client as service_client
from tests.identity.test_service import RecordingEmailClient
from tests.news.conftest import RecordingSummarizer
from tests.tasks.conftest import Clock


@pytest.fixture
def database(service_client: Client) -> Database:
    return service_client.get_database("news")


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def summarizer() -> RecordingSummarizer:
    return RecordingSummarizer()


@pytest.fixture
async def tasks(service_client: Client, clock: Clock) -> TaskService:
    tasks = TaskService(service_client, clock=clock)
    await tasks.init()
    return tasks


@pytest.fixture
async def service(service_client, clock, summarizer, tasks) -> Service:
    service = Service(
        service_client,
        tasks,
        clock=clock,
        summarizer=summarizer,
    )
    await service.init()
    return service


@pytest.fixture
async def claims(service_client: Client) -> UserClaims:
    user = User.create(uuid4(), "live@example.com")
    await Repository(User, service_client.get_database("identity")).save(user)
    return UserClaims(
        id=UUID(user.id),
        role=UserRole.PERMANENT,
        token_generation=user.token_generation,
    )


async def execute(service: Service, tasks: TaskService, claims: UserClaims):
    task = await tasks.claim(
        service.task_id(claims.id), "live", timedelta(minutes=10)
    )
    assert task is not None and task.claim_token is not None
    await service.run(task)
    await tasks.finish(task.id, task.claim_token)


async def test_live_concurrent_limit_and_reservations(
    service, tasks, claims, details, clock, summarizer
):
    for _ in range(4):
        await service.create_topic(claims, details)
    results = await asyncio.gather(
        service.create_topic(claims, details),
        service.create_topic(claims, details),
        return_exceptions=True,
    )
    assert (
        sum(isinstance(result, TopicLimitReached) for result in results) == 1
    )
    topics = await service.list_topics(claims)
    assert len(topics) == 5
    clock.now = topics[0].next_run_at
    task = await tasks.claim(
        service.task_id(claims.id), "live", timedelta(minutes=10)
    )
    assert task is not None
    await asyncio.gather(service.run(task), service.run(task))
    assert len(summarizer.calls) == 5
    assert await service.get_usage(claims) == 5
    assert len({key for _, key in summarizer.calls}) == 5


async def test_live_partitioned_workers(
    service, tasks, service_client, details, clock, summarizer
):
    owners = []
    for index in range(2):
        partition = Partition(index, 2)
        user = User.create(uuid4(), f"worker{index}@example.com")
        while not partition.owns(user.id):
            user = User.create(uuid4(), f"worker{index}@example.com")
        await Repository(User, service_client.get_database("identity")).save(
            user
        )
        owner = UserClaims(
            id=UUID(user.id),
            role=UserRole.PERMANENT,
            token_generation=user.token_generation,
        )
        owners.append(owner)
        topic = await service.create_topic(owner, details)
    clock.now = topic.next_run_at
    workers = [
        Worker(tasks, {TASK_KIND: service.run}, partition=Partition(index, 2))
        for index in range(2)
    ]
    await asyncio.gather(*(worker._tick() for worker in workers))
    async with asyncio.timeout(15):
        await asyncio.gather(
            *(
                execution
                for worker in workers
                for execution in worker._running.values()
            )
        )
    assert len(summarizer.calls) == 2
    for owner in owners:
        task = await tasks.get(service.task_id(owner.id))
        assert task.succeeded_runs == 1
        assert task.status == "pending"
        topic = (await service.list_topics(owner))[0]
        assert (
            len((await service.list_stories(owner, topic.id))[0].stories) == 2
        )


async def test_live_story_pagination(service, tasks, claims, details, clock):
    topic = await service.create_topic(claims, details)
    clock.now = topic.next_run_at
    await execute(service, tasks, claims)
    first_day = clock.now.date()
    clock.now += timedelta(days=1)
    await execute(service, tasks, claims)
    newest = await service.list_stories(claims, topic.id, limit=1)
    assert len(newest) == 1 and newest[0].day == clock.now.date()
    older = await service.list_stories(
        claims, topic.id, before=newest[0].day, limit=1
    )
    assert len(older) == 1 and older[0].day == first_day
    assert await service.list_stories(claims, topic.id, before=first_day) == []


async def test_live_divergent_account_blocks_ai(
    service, tasks, claims, details, clock, summarizer, database, client
):
    topic = await service.create_topic(claims, details)
    clock.now = topic.next_run_at
    document = await database.get(service.account_id(claims.id))
    root = document["_rev"].split("-", 1)[1]
    branches = [
        {
            **document,
            "_rev": f"2-{revision}",
            "_revisions": {"start": 2, "ids": [revision, root]},
        }
        for revision in ("a" * 32, "b" * 32)
    ]
    response = await client.post(
        f"/{database.name}/_bulk_docs",
        json={"new_edits": False, "docs": branches},
    )
    response.raise_for_status()
    with pytest.raises(UnresolvedDocumentConflict):
        await execute(service, tasks, claims)
    assert summarizer.calls == []


async def test_live_app_startup_email_signin_and_shutdown(
    database, monkeypatch, details
):
    monkeypatch.setenv(
        "COUCHDB_DATABASE_PREFIX", database.name.removesuffix("-news")
    )
    monkeypatch.setenv(
        "DIGESTIFY_API_SECRET_KEY", "live-test-secret-at-least-32-characters"
    )
    email = RecordingEmailClient()
    monkeypatch.setattr("digestify_api.app.ConsoleEmailClient", lambda: email)
    app = create_app(Settings(email_backend="console", run_worker=True))
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            base_url="http://api", transport=httpx.ASGITransport(app=app)
        ) as api:
            assert (await api.get("/docs")).status_code == 200
            response = await api.post(
                "/identity/sign-in-with-email",
                json={"email": "startup@example.com"},
            )
            assert response.status_code == 202
            response = await api.post(
                "/identity/verify-sign-in-code",
                json={"email": "startup@example.com", "code": email.last_code},
            )
            assert response.status_code == 200
            access_token = response.json()["access_token"]
            response = await api.post(
                "/news/create-topic",
                json=details.model_dump(mode="json"),
                headers={"Authorization": f"Bearer {access_token}"},
            )
            assert response.status_code == 201


async def test_live_documents_stay_in_their_boundary(
    service, tasks, service_client, claims, details, clock
):
    topic = await service.create_topic(claims, details)
    clock.now = topic.next_run_at
    await execute(service, tasks, claims)
    expected = {
        "identity": {"user"},
        "news": {"topic_account", "story_batch"},
        "tasks": {"task"},
    }
    for name, types in expected.items():
        documents = await service_client.get_database(name).find(
            {"type": {"$exists": True}}
        )
        assert {document["type"] for document in documents} == types

    users = Repository(User, service_client.get_database("identity"))
    user = await users.get(str(claims.id))
    assert user is not None
    user.delete()
    await users.save(user)
    clock.now += timedelta(days=1)
    await execute(service, tasks, claims)
    batches = await service_client.get_database("news").find(
        {"type": "story_batch"}
    )
    assert len(batches) == 1
