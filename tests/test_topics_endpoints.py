from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from digestify_api import news
from digestify_api.infrastructure.couchdb import Document, DocumentRepository, T
from digestify_api.infrastructure.token_generation import (
    TokenGenerator,
    TokenGeneratorSettings,
    UserClaims,
    UserRole,
)
from digestify_api.infrastructure.token_verification import (
    TokenVerifier,
    TokenVerifierSettings,
)
from digestify_api.news.active_topics import MAX_ACTIVE_TOPICS, ActiveTopics
from digestify_api.news.dependencies import Context
from digestify_api.news.quota import FetchQuota
from digestify_api.news.story import Story
from digestify_api.news.topic import Topic
from digestify_api.news.user import User

SECRET_KEY = "test-secret-key"


class InMemoryRepository(DocumentRepository[T]):
    def __init__(self, document_type: type[T]) -> None:
        self._document_type = document_type
        self._documents: dict[str, str] = {}

    async def get(self, id: str) -> T | None:
        stored = self._documents.get(id)
        if stored is None:
            return None
        return self._document_type.model_validate_json(stored)

    async def save(self, document: Document) -> None:
        self._documents[document.id] = document.model_dump_json(by_alias=True)

    async def find(
        self,
        selector: dict[str, Any],
        *,
        sort: list[dict[str, str]] | None = None,
        limit: int | None = None,
    ) -> list[T]:
        matches = [
            doc
            for doc in (
                self._document_type.model_validate_json(stored)
                for stored in self._documents.values()
            )
            if all(getattr(doc, key) == value for key, value in selector.items())
        ]
        if limit is not None:
            matches = matches[:limit]
        return matches


@pytest.fixture
def active_topics() -> InMemoryRepository[ActiveTopics]:
    return InMemoryRepository(ActiveTopics)


@pytest.fixture
def token_generator() -> TokenGenerator:
    return TokenGenerator(TokenGeneratorSettings(secret_key=SecretStr(SECRET_KEY)))


@pytest.fixture
def client(active_topics: InMemoryRepository[ActiveTopics]) -> TestClient:
    app = FastAPI()
    app.include_router(news.api_router, prefix="/news")
    app.state.news_context = Context(
        users=InMemoryRepository(User),
        topics=InMemoryRepository(Topic),
        stories=InMemoryRepository(Story),
        quotas=InMemoryRepository(FetchQuota),
        active_topics=active_topics,
        token_verifier=TokenVerifier(
            TokenVerifierSettings(secret_key=SecretStr(SECRET_KEY))
        ),
    )
    return TestClient(app)


def auth_header(token_generator: TokenGenerator, user_id: UUID) -> dict[str, str]:
    pair = token_generator.generate(UserClaims(id=user_id, role=UserRole.PERMANENT))
    return {"Authorization": f"Bearer {pair.access_token}"}


def create_topic(
    client: TestClient, headers: dict[str, str], name: str = "Topic"
) -> dict[str, Any]:
    response = client.post(
        "/news/create-topic",
        headers=headers,
        json={
            "name": name,
            "description": "desc",
            "language": "en-US",
            "schedule": {"time": "09:00:00", "timezone": "UTC"},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_create_topic_auto_activates_below_cap(
    client: TestClient, token_generator: TokenGenerator
) -> None:
    headers = auth_header(token_generator, uuid4())
    body = create_topic(client, headers)
    assert body["is_active"] is True


def test_create_topic_stays_inactive_at_cap(
    client: TestClient, token_generator: TokenGenerator
) -> None:
    headers = auth_header(token_generator, uuid4())
    for index in range(MAX_ACTIVE_TOPICS):
        assert create_topic(client, headers, name=f"Topic {index}")["is_active"] is True

    overflow = create_topic(client, headers, name="One too many")
    assert overflow["is_active"] is False


async def test_active_set_never_exceeds_cap(
    client: TestClient,
    token_generator: TokenGenerator,
    active_topics: InMemoryRepository[ActiveTopics],
) -> None:
    user_id = uuid4()
    headers = auth_header(token_generator, user_id)
    for index in range(MAX_ACTIVE_TOPICS + 3):
        create_topic(client, headers, name=f"Topic {index}")

    activation = await active_topics.get(ActiveTopics.id_for(user_id))
    assert activation is not None
    assert len(activation.topic_ids) == MAX_ACTIVE_TOPICS


def test_activate_at_cap_is_rejected(
    client: TestClient, token_generator: TokenGenerator
) -> None:
    headers = auth_header(token_generator, uuid4())
    for index in range(MAX_ACTIVE_TOPICS):
        create_topic(client, headers, name=f"Topic {index}")

    inactive = create_topic(client, headers, name="Inactive")
    assert inactive["is_active"] is False

    response = client.post(
        "/news/activate-topic",
        headers=headers,
        json={"topic_id": inactive["id"]},
    )
    assert response.status_code == 409


def test_deactivate_then_activate_other(
    client: TestClient, token_generator: TokenGenerator
) -> None:
    headers = auth_header(token_generator, uuid4())
    active = [
        create_topic(client, headers, name=f"Topic {i}")
        for i in range(MAX_ACTIVE_TOPICS)
    ]
    inactive = create_topic(client, headers, name="Inactive")
    assert inactive["is_active"] is False

    freed = client.post(
        "/news/deactivate-topic",
        headers=headers,
        json={"topic_id": active[0]["id"]},
    )
    assert freed.status_code == 200
    assert freed.json()["is_active"] is False

    promoted = client.post(
        "/news/activate-topic",
        headers=headers,
        json={"topic_id": inactive["id"]},
    )
    assert promoted.status_code == 200
    assert promoted.json()["is_active"] is True


def test_activate_is_idempotent(
    client: TestClient, token_generator: TokenGenerator
) -> None:
    headers = auth_header(token_generator, uuid4())
    topic = create_topic(client, headers)

    again = client.post(
        "/news/activate-topic",
        headers=headers,
        json={"topic_id": topic["id"]},
    )
    assert again.status_code == 200
    assert again.json()["is_active"] is True


def test_topic_activation_is_per_user(
    client: TestClient, token_generator: TokenGenerator
) -> None:
    first = auth_header(token_generator, uuid4())
    second = auth_header(token_generator, uuid4())

    for index in range(MAX_ACTIVE_TOPICS):
        create_topic(client, first, name=f"First {index}")

    # The second user has their own budget, so their first topic still activates.
    body = create_topic(client, second, name="Second user topic")
    assert body["is_active"] is True
