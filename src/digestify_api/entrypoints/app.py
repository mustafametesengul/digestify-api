from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from digestify_api.dependencies import (
    AuthSettings,
    DBSettings,
    OpenAISettings,
    TaskProcessor,
    init_auth_manager,
    init_db,
    init_openai,
)
from digestify_api.routers import (
    auth_router,
    follows_router,
    stories_router,
    topics_router,
)
from digestify_api.tasks import stories_task_registry


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_prefix="DIGESTIFY_API_",
    )

    debug: bool = Field(default=False)
    host: str = Field(default="localhost")
    port: int = Field(default=8000)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    db: DBSettings = Field(default_factory=DBSettings)
    openai: OpenAISettings = Field(default_factory=OpenAISettings)


_settings: AppSettings | None = None


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    global _settings
    if _settings is None:
        raise ValueError("AppSettings have not been initialized.")

    db = init_db(_settings.db)
    await db.init_pool()

    init_openai(settings=_settings.openai)

    task_processor = TaskProcessor(db)
    task_processor.add_registry(stories_task_registry)
    await task_processor.start()

    init_auth_manager(_settings.auth)

    try:
        yield
    finally:
        await task_processor.stop()
        await db.close_pool()


def app_main(settings: AppSettings | None = None) -> None:
    global _settings
    _settings = settings or AppSettings()

    app = FastAPI(
        title="Digestify API",
        lifespan=lifespan,
        debug=_settings.debug,
    )

    app.include_router(auth_router)
    app.include_router(topics_router)
    app.include_router(follows_router)
    app.include_router(stories_router)

    uvicorn.run(app, host=_settings.host, port=_settings.port)


if __name__ == "__main__":
    app_main()
