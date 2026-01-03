from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from digestify_api.auth import fetch_jwks, get_auth, mock_get_auth
from digestify_api.db import dispose_engine, init_engine
from digestify_api.following.router import router as following_router
from digestify_api.settings import get_settings, init_settings
from digestify_api.topics.router import router as topics_router
from digestify_api.users.router import router as users_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    init_engine()
    if not settings.debug:
        await fetch_jwks()
    try:
        yield
    finally:
        await dispose_engine()


def create_app() -> FastAPI:
    init_settings()
    settings = get_settings()

    app = FastAPI(
        title="Digestify API",
        lifespan=lifespan,
        debug=settings.debug,
    )
    app.include_router(users_router)
    app.include_router(following_router)
    app.include_router(topics_router)

    if settings.debug:
        app.dependency_overrides[get_auth] = mock_get_auth

    return app


app = create_app()
