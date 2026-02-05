from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from digestify_api import dependencies, routers, tasks


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_prefix="DIGESTIFY_API_",
    )

    debug: bool = Field(default=False)
    host: str = Field(default="localhost")
    port: int = Field(default=8000)
    auth: dependencies.auth.AuthSettings = Field(
        default_factory=dependencies.auth.AuthSettings
    )
    db: dependencies.db.DBSettings = Field(default_factory=dependencies.db.DBSettings)
    openai: dependencies.openai.OpenAISettings = Field(
        default_factory=dependencies.openai.OpenAISettings
    )


_settings: AppSettings | None = None


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    global _settings
    if _settings is None:
        raise ValueError("AppSettings have not been initialized.")

    db = dependencies.db.init_db_manager(_settings.db)
    await db.init_pool()

    dependencies.openai.init_openai(settings=_settings.openai)

    task_processor_ = dependencies.tasks.TaskProcessor(db)
    task_processor_.add_registry(tasks.stories.task_registry)
    await task_processor_.start()

    dependencies.auth.init_auth_manager(_settings.auth)

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

    app.include_router(routers.auth.router)
    app.include_router(routers.topics.router)
    app.include_router(routers.follows.router)
    app.include_router(routers.stories.router)

    uvicorn.run(app, host=_settings.host, port=_settings.port)


if __name__ == "__main__":
    app_main()
