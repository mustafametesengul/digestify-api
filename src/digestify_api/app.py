from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from digestify_api.auth import AuthSettings, fetch_jwks, get_auth, mock_get_auth
from digestify_api.db import DBSettings, dispose_engine, init_engine
from digestify_api.following.router import router as following_router
from digestify_api.topics.router import router as topics_router
from digestify_api.users.router import router as users_router


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    debug: bool = Field(default=...)
    auth_settings: AuthSettings | None = Field(default=None)
    db_settings: DBSettings = Field(default_factory=DBSettings)
    openai_api_key: str = Field(default=...)


_settings: AppSettings | None = None


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    global _settings
    if _settings is None:
        raise ValueError("AppSettings have not been initialized.")
    init_engine(_settings.db_settings)
    if not _settings.debug:
        if _settings.auth_settings is None:
            raise ValueError("AuthSettings must be provided in non-debug mode.")
        await fetch_jwks(_settings.auth_settings)
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

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    run_app()
