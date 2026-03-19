from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from digestify_api import identity, news


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_prefix="DIGESTIFY_API_",
    )

    debug: bool = Field(default=False)
    host: str = Field(default="localhost")
    port: int = Field(default=8000)


settings = AppSettings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with (
        identity.lifespan(name="identity") as identity_context,
        news.lifespan(name="news") as news_context,
    ):
        app.state.identity_context = identity_context
        app.state.news_context = news_context
        yield


def run_app() -> None:
    app = FastAPI(
        title="Digestify API",
        lifespan=lifespan,
        debug=settings.debug,
    )

    app.include_router(identity.router, prefix="/identity", tags=["identity"])
    app.include_router(news.router, prefix="/news", tags=["news"])

    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    run_app()
