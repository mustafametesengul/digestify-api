from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from digestify_api.couchdb import Database, Repository
from digestify_api.identity.router import router
from digestify_api.identity.service import Service
from digestify_api.identity.sign_in_code import SignInCode
from digestify_api.identity.token import (
    TokenGenerator,
    TokenGeneratorSettings,
    TokenVerifier,
    TokenVerifierSettings,
)
from digestify_api.identity.user import User
from tests.identity.test_service import (
    EMAIL,
    SECRET,
    InMemoryCouch,
    RecordingEmailClient,
)


@dataclass
class Api:
    client: httpx.AsyncClient
    email: RecordingEmailClient
    sign_in_codes: Repository[SignInCode]

    async def sign_in(self, email: str = EMAIL) -> dict[str, str]:
        """Complete a full email sign-in over HTTP and return the token pair."""
        await self.reset_cooldown(email)
        response = await self.client.post(
            "/identity/sign-in-with-email",
            json={"email": email},
        )
        assert response.status_code == 202, response.text
        response = await self.client.post(
            "/identity/verify-sign-in-code",
            json={"email": email, "code": self.email.last_code},
        )
        assert response.status_code == 200, response.text
        return response.json()

    async def reset_cooldown(self, email: str = EMAIL) -> None:
        sign_in = await self.sign_in_codes.get(SignInCode.id_for(email))
        if sign_in is not None:
            sign_in.last_issued_at = None
            await self.sign_in_codes.save(sign_in)


def bearer(tokens: dict[str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture
async def api() -> AsyncIterator[Api]:
    async with httpx.AsyncClient(
        base_url="http://couch",
        transport=httpx.MockTransport(InMemoryCouch()),
    ) as couch_client:
        database = Database(couch_client, "identity")
        users = Repository(User, database)
        sign_in_codes = Repository(SignInCode, database)
        email = RecordingEmailClient()

        app = FastAPI()
        app.include_router(router)
        app.state.identity_service = Service(
            users=users,
            sign_in_codes=sign_in_codes,
            email_sender=email,
            token_generator=TokenGenerator(
                TokenGeneratorSettings(secret_key=SecretStr(SECRET)),
            ),
            token_verifier=TokenVerifier(
                TokenVerifierSettings(secret_key=SecretStr(SECRET)),
            ),
        )
        app.state.identity_token_verifier = TokenVerifier(
            TokenVerifierSettings(secret_key=SecretStr(SECRET)),
        )

        async with httpx.AsyncClient(
            base_url="http://api",
            transport=httpx.ASGITransport(app=app),
        ) as client:
            yield Api(client=client, email=email, sign_in_codes=sign_in_codes)


async def test_sign_in_anonymously_returns_token_pair(api: Api) -> None:
    response = await api.client.post("/identity/sign-in-anonymously")

    assert response.status_code == 200
    tokens = response.json()
    assert tokens["token_type"] == "Bearer"
    assert tokens["access_token"]
    assert tokens["refresh_token"]


async def test_email_sign_in_flow_returns_account(api: Api) -> None:
    tokens = await api.sign_in("Alice@Example.COM")

    response = await api.client.get("/identity/account", headers=bearer(tokens))

    assert response.status_code == 200
    assert response.json() == {"email": EMAIL}


async def test_sign_in_with_email_cooldown_returns_429(api: Api) -> None:
    first = await api.client.post(
        "/identity/sign-in-with-email",
        json={"email": EMAIL},
    )
    assert first.status_code == 202

    second = await api.client.post(
        "/identity/sign-in-with-email",
        json={"email": EMAIL},
    )

    assert second.status_code == 429
    assert second.headers["Retry-After"] == "60"


async def test_verify_sign_in_code_rejects_wrong_code(api: Api) -> None:
    await api.client.post("/identity/sign-in-with-email", json={"email": EMAIL})
    wrong = "000000" if api.email.last_code != "000000" else "999999"

    response = await api.client.post(
        "/identity/verify-sign-in-code",
        json={"email": EMAIL, "code": wrong},
    )

    assert response.status_code == 401


async def test_verify_sign_in_code_rejects_malformed_code(api: Api) -> None:
    response = await api.client.post(
        "/identity/verify-sign-in-code",
        json={"email": EMAIL, "code": "abc"},
    )

    assert response.status_code == 422


async def test_refresh_token_returns_new_pair(api: Api) -> None:
    tokens = await api.sign_in()

    response = await api.client.post(
        "/identity/refresh-token",
        json={"refresh_token": tokens["refresh_token"]},
    )

    assert response.status_code == 200
    assert response.json()["access_token"]


async def test_refresh_token_rejects_access_token(api: Api) -> None:
    tokens = await api.sign_in()

    response = await api.client.post(
        "/identity/refresh-token",
        json={"refresh_token": tokens["access_token"]},
    )

    assert response.status_code == 401


async def test_account_requires_credentials(api: Api) -> None:
    response = await api.client.get("/identity/account")

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


async def test_account_rejects_garbage_token(api: Api) -> None:
    response = await api.client.get(
        "/identity/account",
        headers={"Authorization": "Bearer garbage"},
    )

    assert response.status_code == 401


async def test_account_forbidden_for_anonymous_user(api: Api) -> None:
    response = await api.client.post("/identity/sign-in-anonymously")
    tokens = response.json()

    response = await api.client.get("/identity/account", headers=bearer(tokens))

    assert response.status_code == 403


async def test_delete_account_revokes_access(api: Api) -> None:
    tokens = await api.sign_in()

    response = await api.client.delete("/identity/account", headers=bearer(tokens))
    assert response.status_code == 204

    response = await api.client.get("/identity/account", headers=bearer(tokens))
    assert response.status_code == 401
