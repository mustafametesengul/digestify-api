import re
from datetime import timedelta
from typing import Any
from uuid import UUID

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from digestify_api import identity
from digestify_api.identity import sign_in_code
from digestify_api.identity.dependencies import Context
from digestify_api.identity.sign_in_code import SignInCode
from digestify_api.identity.user import User
from digestify_api.infrastructure.couchdb import Document, DocumentRepository, T
from digestify_api.infrastructure.token_generation import (
    TokenGenerator,
    TokenGeneratorSettings,
)
from digestify_api.infrastructure.token_verification import (
    TokenVerifier,
    TokenVerifierSettings,
)

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


class FakeEmailSender:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    async def send(self, to: str, subject: str, text: str) -> None:
        self.sent.append((to, subject, text))

    def last_code(self) -> str:
        _, _, text = self.sent[-1]
        match = re.search(r"\d{6}", text)
        assert match is not None
        return match.group()


@pytest.fixture
def email_sender() -> FakeEmailSender:
    return FakeEmailSender()


@pytest.fixture
def client(email_sender: FakeEmailSender) -> TestClient:
    app = FastAPI()
    app.include_router(identity.api_router, prefix="/identity")
    app.state.identity_context = Context(
        users=InMemoryRepository(User),
        sign_in_codes=InMemoryRepository(SignInCode),
        email_sender=email_sender,
        token_generator=TokenGenerator(
            TokenGeneratorSettings(secret_key=SecretStr(SECRET_KEY))
        ),
        token_verifier=TokenVerifier(
            TokenVerifierSettings(secret_key=SecretStr(SECRET_KEY))
        ),
    )
    return TestClient(app)


def user_id_from(access_token: str) -> UUID:
    payload = jwt.decode(access_token, SECRET_KEY, algorithms=["HS256"])
    return UUID(payload["sub"])


def test_sign_in_sends_code_to_email(
    client: TestClient, email_sender: FakeEmailSender
) -> None:
    response = client.post(
        "/identity/sign-in-with-email",
        json={"email": "mete@example.com"},
    )

    assert response.status_code == 202
    [(to, subject, text)] = email_sender.sent
    assert to == "mete@example.com"
    assert re.search(r"\d{6}", text) is not None


def test_verify_with_correct_code_returns_tokens(
    client: TestClient, email_sender: FakeEmailSender
) -> None:
    client.post("/identity/sign-in-with-email", json={"email": "mete@example.com"})

    response = client.post(
        "/identity/verify-sign-in-code",
        json={"email": "mete@example.com", "code": email_sender.last_code()},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "Bearer"
    assert user_id_from(body["access_token"]) is not None


def test_verify_with_wrong_code_is_rejected(client: TestClient) -> None:
    client.post("/identity/sign-in-with-email", json={"email": "mete@example.com"})

    response = client.post(
        "/identity/verify-sign-in-code",
        json={"email": "mete@example.com", "code": "000000"},
    )

    assert response.status_code == 401


def test_code_is_single_use(client: TestClient, email_sender: FakeEmailSender) -> None:
    client.post("/identity/sign-in-with-email", json={"email": "mete@example.com"})
    code = email_sender.last_code()

    payload = {"email": "mete@example.com", "code": code}
    assert client.post("/identity/verify-sign-in-code", json=payload).status_code == 200
    assert client.post("/identity/verify-sign-in-code", json=payload).status_code == 401


def test_signing_in_again_returns_same_user(
    client: TestClient,
    email_sender: FakeEmailSender,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sign_in_code, "ISSUE_COOLDOWN", timedelta(0))
    user_ids = []
    for _ in range(2):
        client.post("/identity/sign-in-with-email", json={"email": "mete@example.com"})
        response = client.post(
            "/identity/verify-sign-in-code",
            json={"email": "mete@example.com", "code": email_sender.last_code()},
        )
        user_ids.append(user_id_from(response.json()["access_token"]))

    assert user_ids[0] == user_ids[1]


def test_email_is_case_insensitive(
    client: TestClient, email_sender: FakeEmailSender
) -> None:
    client.post("/identity/sign-in-with-email", json={"email": "Mete@Example.com"})

    response = client.post(
        "/identity/verify-sign-in-code",
        json={"email": "mete@example.com", "code": email_sender.last_code()},
    )

    assert response.status_code == 200


def test_requesting_codes_too_quickly_is_throttled(client: TestClient) -> None:
    payload = {"email": "mete@example.com"}
    assert client.post("/identity/sign-in-with-email", json=payload).status_code == 202
    assert client.post("/identity/sign-in-with-email", json=payload).status_code == 429
