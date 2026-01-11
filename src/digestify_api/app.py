from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from digestify_api.auth import AuthSettings, fetch_jwks, get_auth, mock_get_auth
from digestify_api.db import DBSettings, create_engine, dispose_engine
from digestify_api.following.router import following_router
from digestify_api.topics.router import topics_router
from digestify_api.users.router import users_router


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_prefix="DIGESTIFY_API_",
    )

    debug: bool = Field(default=False)
    host: str = Field(default="localhost")
    port: int = Field(default=8000)
    auth: AuthSettings | None = Field(default=None)
    db: DBSettings = Field(default_factory=DBSettings)


_settings: AppSettings | None = None


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    global _settings
    if _settings is None:
        raise ValueError("AppSettings have not been initialized.")
    create_engine(_settings.db)
    if not _settings.debug:
        if _settings.auth is None:
            raise ValueError("AuthSettings must be provided in non-debug mode.")
        await fetch_jwks(_settings.auth)
    try:
        yield
    finally:
        await dispose_engine()


def run_app(settings: AppSettings | None = None) -> None:
    global _settings
    _settings = settings or AppSettings()
    app = FastAPI(
        title="Digestify API",
        lifespan=lifespan,
        debug=_settings.debug,
    )
    app.include_router(users_router)
    app.include_router(following_router)
    app.include_router(topics_router)

    if _settings.debug:
        app.dependency_overrides[get_auth] = mock_get_auth

    uvicorn.run(app, host=_settings.host, port=_settings.port)


if __name__ == "__main__":
    run_app()
