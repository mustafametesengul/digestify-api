from typing import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from digestify_api import dependencies, routers


@pytest.fixture
def auth_manager() -> dependencies.auth.AuthManager:
    settings = dependencies.auth.AuthSettings(
        secret_key=SecretStr("test-secret-key-that-is-at-least-32-bytes-long"),
        access_token_expire_minutes=30,
        refresh_token_expire_days=7,
    )
    return dependencies.auth.AuthManager(settings)


@pytest.fixture
def app(
    db: dependencies.db.DBManager,
    auth_manager: dependencies.auth.AuthManager,
) -> FastAPI:
    app = FastAPI()
    app.include_router(routers.auth.router)

    app.dependency_overrides[dependencies.db.get_db_manager] = lambda: db
    app.dependency_overrides[dependencies.auth.get_auth_manager] = lambda: auth_manager
    return app


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
