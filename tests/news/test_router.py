from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import httpx
import pytest
from pydantic import SecretStr

from digestify_api.app import Settings, connect_services, create_app
from digestify_api.couchdb import Client, Repository
from digestify_api.identity.service import Service as IdentityService
from digestify_api.identity.sign_in_code import SignInCode
from digestify_api.identity.token import (
    TokenGenerator,
    TokenGeneratorSettings,
    TokenVerifier,
    TokenVerifierSettings,
    UserClaims,
    UserRole,
)
from digestify_api.identity.user import User
from tests.identity.test_service import RecordingEmailClient
from tests.news.conftest import Context

SECRET = SecretStr("topics-test-secret-with-at-least-32-bytes")


def headers(claims: UserClaims) -> dict[str, str]:
    tokens = TokenGenerator(
        TokenGeneratorSettings(secret_key=SECRET)
    ).generate(claims)
    return {"Authorization": f"Bearer {tokens.access_token}"}


@pytest.fixture
async def api(context: Context) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app()
    verifier = TokenVerifier(TokenVerifierSettings(secret_key=SECRET))
    app.state.identity_token_verifier = verifier
    app.state.identity_service = IdentityService(
        context.users,
        Repository(SignInCode, context.service._database),
        RecordingEmailClient(),
        TokenGenerator(TokenGeneratorSettings(secret_key=SECRET)),
        verifier,
    )
    app.state.news_service = context.service
    async with httpx.AsyncClient(
        base_url="http://api", transport=httpx.ASGITransport(app=app)
    ) as client:
        yield client


async def test_swagger_contains_both_routers(api):
    response = await api.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "/identity/sign-in-with-email" in schema["paths"]
    actions = {
        "create-topic",
        "list-topics",
        "get-topic",
        "update-topic",
        "delete-topic",
        "list-stories",
        "get-usage",
    }
    paths = schema["paths"]
    assert {path for path in paths if path.startswith("/news")} == {
        f"/news/{action}" for action in actions
    }
    assert not any(path.startswith("/topics") for path in paths)
    for action in actions:
        operations = paths[f"/news/{action}"]
        assert set(operations) == {"post"}
        assert operations["post"]["security"] == [{"HTTPBearer": []}]
        assert operations["post"]["tags"] == ["news"]
        assert not operations["post"].get("parameters")
    for action in (
        "create-topic",
        "get-topic",
        "update-topic",
        "delete-topic",
        "list-stories",
    ):
        assert paths[f"/news/{action}"]["post"]["requestBody"]["required"]
    assert (await api.get("/docs")).status_code == 200


@pytest.mark.parametrize("status", [401, 409, 500, 503])
async def test_startup_retries_only_transient_errors(
    context, monkeypatch, status
):
    @asynccontextmanager
    async def connect():
        yield Client(context.service._database._http_client)

    monkeypatch.setattr("digestify_api.app.Client.connect", connect)
    response = httpx.Response(
        status, request=httpx.Request("POST", "http://couch/tasks/_index")
    )
    error = httpx.HTTPStatusError(
        "Initialization failed", request=response.request, response=response
    )
    initialize = AsyncMock(side_effect=[error, None])
    sleep = AsyncMock()
    monkeypatch.setattr("digestify_api.app.TaskService.init", initialize)
    monkeypatch.setattr("digestify_api.app.asyncio.sleep", sleep)
    if status == 401:
        with pytest.raises(httpx.HTTPStatusError):
            async with connect_services(Settings(database="tasks")):
                pytest.fail("Unauthorized initialization must not succeed")
        sleep.assert_not_awaited()
        assert initialize.await_count == 1
    else:
        async with connect_services(Settings(database="tasks")):
            assert initialize.await_count == 2
        sleep.assert_awaited_once_with(1)


async def test_routes_crud_usage_and_stories(api, context, details):
    auth = headers(context.claims)
    payload = details.model_dump(mode="json")
    response = await api.post("/news/create-topic", json=payload, headers=auth)
    assert response.status_code == 201
    topic_id = response.json()["id"]
    identity = {"topic_id": topic_id}
    response = await api.post("/news/get-topic", json=identity, headers=auth)
    assert response.json()["id"] == topic_id
    assert len((await api.post("/news/list-topics", headers=auth)).json()) == 1
    response = await api.post(
        "/news/update-topic",
        json={**payload, **identity, "name": "Updated"},
        headers=auth,
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated"
    topic = await context.service.get_topic(context.claims, UUID(topic_id))
    context.clock.now = topic.next_run_at
    await context.run()
    response = await api.post(
        "/news/list-stories", json=identity, headers=auth
    )
    assert response.status_code == 200
    assert len(response.json()[0]["stories"]) == 2
    assert "_rev" not in response.json()[0]
    assert (await api.post("/news/get-usage", headers=auth)).json() == {
        "daily_limit": 5,
        "used": 1,
    }
    response = await api.post(
        "/news/delete-topic", json=identity, headers=auth
    )
    assert response.status_code == 204
    for action in ("get-topic", "list-stories"):
        response = await api.post(
            f"/news/{action}", json=identity, headers=auth
        )
        assert response.status_code == 404


async def test_unauthenticated_anonymous_and_refresh_tokens(
    api, context, details
):
    payload = details.model_dump(mode="json")
    response = await api.post("/news/create-topic", json=payload)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    anonymous = await api.post("/identity/sign-in-anonymously")
    response = await api.post(
        "/news/create-topic",
        json=payload,
        headers={
            "Authorization": f"Bearer {anonymous.json()['access_token']}"
        },
    )
    assert response.status_code == 403
    tokens = TokenGenerator(
        TokenGeneratorSettings(secret_key=SECRET)
    ).generate(context.claims)
    response = await api.post(
        "/news/create-topic",
        json=payload,
        headers={"Authorization": f"Bearer {tokens.refresh_token}"},
    )
    assert response.status_code == 401


async def test_cross_user_access_including_admin_is_hidden(
    api, context, details
):
    topic = await context.service.create_topic(context.claims, details)
    other = User.create(uuid4(), "other@example.com")
    await context.users.save(other)
    claims = UserClaims(
        id=UUID(other.id),
        role=UserRole.ADMIN,
        token_generation=other.token_generation,
    )
    auth = headers(claims)
    identity = {"topic_id": str(topic.id)}
    for action, payload in (
        ("get-topic", identity),
        ("update-topic", {**details.model_dump(mode="json"), **identity}),
        ("delete-topic", identity),
        ("list-stories", identity),
    ):
        response = await api.post(
            f"/news/{action}", headers=auth, json=payload
        )
        assert response.status_code == 404
    assert (await api.post("/news/list-topics", headers=auth)).json() == []


async def test_limit_validation_and_conflict_errors(api, context, details):
    auth = headers(context.claims)
    payload = details.model_dump(mode="json")
    response = await api.post(
        "/news/create-topic",
        json={**payload, "user_id": str(uuid4())},
        headers=auth,
    )
    assert response.status_code == 422
    for _ in range(5):
        assert (
            await api.post("/news/create-topic", json=payload, headers=auth)
        ).status_code == 201
    assert (
        await api.post("/news/create-topic", json=payload, headers=auth)
    ).status_code == 409
    identity = context.service.account_id(context.claims.id)
    context.couch.docs[identity]["_conflicts"] = ["2-divergent"]
    response = await api.post("/news/list-topics", headers=auth)
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "5"


@pytest.mark.parametrize(
    ("action", "payload"),
    [
        ("get-topic", {}),
        ("delete-topic", {"topic_id": "invalid"}),
        ("update-topic", {"topic_id": str(uuid4())}),
        ("list-stories", {"topic_id": str(uuid4()), "limit": 0}),
        ("list-stories", {"topic_id": str(uuid4()), "limit": 101}),
        ("list-stories", {"topic_id": str(uuid4()), "before": "invalid"}),
        ("get-topic", {"topic_id": str(uuid4()), "user_id": str(uuid4())}),
    ],
)
async def test_action_payload_validation(api, context, action, payload):
    response = await api.post(
        f"/news/{action}", json=payload, headers=headers(context.claims)
    )
    assert response.status_code == 422
