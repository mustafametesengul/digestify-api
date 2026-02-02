from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from digestify_api.dependencies import (
    auth_manager,
    db_manager,
    openai_client,
    task_processor,
)
from digestify_api.routers import follow_router, story_router, topic_router, user_router
from digestify_api.tasks import story_tasks


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_prefix="DIGESTIFY_API_",
    )

    debug: bool = Field(default=False)
    host: str = Field(default="localhost")
    port: int = Field(default=8000)
    auth: auth_manager.AuthSettings = Field(default_factory=auth_manager.AuthSettings)
    db: db_manager.DBSettings = Field(default_factory=db_manager.DBSettings)
    openai: openai_client.OpenAISettings = Field(
        default_factory=openai_client.OpenAISettings
    )


_settings: AppSettings | None = None


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    global _settings
    if _settings is None:
        raise ValueError("AppSettings have not been initialized.")

    db = db_manager.init_db(_settings.db)
    await db.init_pool()

    openai_client.init_openai(settings=_settings.openai)

    task_processor_ = task_processor.TaskProcessor(db)
    task_processor_.add_registry(story_tasks.story_task_registry)
    await task_processor_.start()

    auth_manager.init_auth_manager(_settings.auth)

    try:
        yield
    finally:
        await task_processor_.stop()
        await db.close_pool()


def app_main(settings: AppSettings | None = None) -> None:
    global _settings
    _settings = settings or AppSettings()

    app = FastAPI(
        title="Digestify API",
        lifespan=lifespan,
        debug=_settings.debug,
    )

    app.include_router(user_router.router)
    app.include_router(topic_router.router)
    app.include_router(follow_router.router)
    app.include_router(story_router.router)

    uvicorn.run(app, host=_settings.host, port=_settings.port)


if __name__ == "__main__":
    app_main()
