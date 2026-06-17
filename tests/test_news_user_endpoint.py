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
from digestify_api.news.active_topics import ActiveTopics
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
        if sort:
            field, direction = next(iter(sort[0].items()))
            matches.sort(
                key=lambda doc: getattr(doc, field), reverse=direction == "desc"
            )
        if limit is not None:
            matches = matches[:limit]
        return matches


@pytest.fixture
def users() -> InMemoryRepository[User]:
    return InMemoryRepository(User)


@pytest.fixture
def token_generator() -> TokenGenerator:
    return TokenGenerator(TokenGeneratorSettings(secret_key=SecretStr(SECRET_KEY)))


@pytest.fixture
def client(users: InMemoryRepository[User]) -> TestClient:
    app = FastAPI()
    app.include_router(news.api_router, prefix="/news")
    app.state.news_context = Context(
        users=users,
        topics=InMemoryRepository(Topic),
        stories=InMemoryRepository(Story),
        quotas=InMemoryRepository(FetchQuota),
        active_topics=InMemoryRepository(ActiveTopics),
        token_verifier=TokenVerifier(
            TokenVerifierSettings(secret_key=SecretStr(SECRET_KEY))
        ),
    )
    return TestClient(app)


def access_token(token_generator: TokenGenerator, user_id: UUID) -> str:
    pair = token_generator.generate(UserClaims(id=user_id, role=UserRole.PERMANENT))
    return pair.access_token


async def test_returns_projected_user(
    client: TestClient,
    users: InMemoryRepository[User],
    token_generator: TokenGenerator,
) -> None:
    user_id = uuid4()
    await users.save(User(id=str(user_id)))

    response = client.get(
        "/news/me",
        headers={"Authorization": f"Bearer {access_token(token_generator, user_id)}"},
    )

    assert response.status_code == 200
    assert response.json() == {"id": str(user_id)}


def test_requires_authentication(client: TestClient) -> None:
    assert client.get("/news/me").status_code == 401


async def test_unknown_user_is_not_found(
    client: TestClient, token_generator: TokenGenerator
) -> None:
    response = client.get(
        "/news/me",
        headers={"Authorization": f"Bearer {access_token(token_generator, uuid4())}"},
    )

    assert response.status_code == 404


async def test_deleted_user_is_not_found(
    client: TestClient,
    users: InMemoryRepository[User],
    token_generator: TokenGenerator,
) -> None:
    user_id = uuid4()
    await users.save(User(id=str(user_id), is_deleted=True))

    response = client.get(
        "/news/me",
        headers={"Authorization": f"Bearer {access_token(token_generator, user_id)}"},
    )

    assert response.status_code == 404
