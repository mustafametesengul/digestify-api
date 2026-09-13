from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID, uuid4

import httpx
import pytest

from digestify_api.couchdb import Client, Repository
from digestify_api.identity.token import UserClaims, UserRole
from digestify_api.identity.user import User
from digestify_api.news.service import Service
from digestify_api.news.story import StoryDraft
from digestify_api.news.topic import Topic, TopicDetails
from digestify_api.tasks import Service as TaskService
from tests.tasks.conftest import Clock, InMemoryCouch


class RecordingSummarizer:
    def __init__(self) -> None:
        self.calls: list[tuple[Topic, str]] = []
        self.error: Exception | None = None

    async def __call__(self, topic: Topic, key: str) -> list[StoryDraft]:
        self.calls.append((topic, key))
        if self.error is not None:
            raise self.error
        return [
            StoryDraft(title="First", body="First story"),
            StoryDraft(title="Second", body="Second story"),
        ]


@dataclass
class Context:
    client: Client
    service: Service
    tasks: TaskService
    users: Repository[User]
    claims: UserClaims
    clock: Clock
    couch: InMemoryCouch
    summarizer: RecordingSummarizer

    async def run(self) -> None:
        task = await self.tasks.claim(
            self.service.task_id(self.claims.id),
            "test-worker",
            timedelta(minutes=10),
        )
        assert task is not None and task.claim_token is not None
        try:
            await self.service.run(task)
        finally:
            await self.tasks.finish(task.id, task.claim_token)


@pytest.fixture
def details() -> TopicDetails:
    return TopicDetails.model_validate(
        {
            "name": "Science",
            "description": "New discoveries",
            "language": "en-US",
            "schedule": {"time": "09:00", "timezone": "UTC"},
        }
    )


@pytest.fixture
async def context() -> AsyncIterator[Context]:
    clock, couch = Clock(), InMemoryCouch()
    async with httpx.AsyncClient(
        base_url="http://couch", transport=httpx.MockTransport(couch)
    ) as client:
        couch_client = Client(client)
        await couch_client.ensure_databases(("identity", "news", "tasks"))
        users = Repository(User, couch_client.get_database("identity"))
        user = User.create(uuid4(), "alice@example.com")
        await users.save(user)
        claims = UserClaims(
            id=UUID(user.id),
            role=UserRole.PERMANENT,
            token_generation=user.token_generation,
        )
        tasks = TaskService(couch_client, clock=clock)
        summarizer = RecordingSummarizer()
        service = Service(
            couch_client, tasks, summarizer=summarizer, clock=clock
        )
        await tasks.init()
        await service.init()
        yield Context(
            couch_client,
            service,
            tasks,
            users,
            claims,
            clock,
            couch,
            summarizer,
        )
