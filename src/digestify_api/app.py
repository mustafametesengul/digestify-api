import argparse
import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from typing import Literal

import httpx
import uvicorn
from fastapi import FastAPI
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from digestify_api.couchdb import Client
from digestify_api.identity.accounts import DATABASE_NAME as IDENTITY_DATABASE
from digestify_api.identity.email import EmailClient
from digestify_api.identity.router import router as identity_router
from digestify_api.identity.service import Service as IdentityService
from digestify_api.identity.token import TokenGenerator, TokenVerifier
from digestify_api.news.router import router as news_router
from digestify_api.news.service import DATABASE_NAME as NEWS_DATABASE
from digestify_api.news.service import TASK_KIND
from digestify_api.news.service import Service as NewsService
from digestify_api.tasks import Partition, Worker
from digestify_api.tasks import Service as TaskService
from digestify_api.tasks.service import DATABASE_NAME as TASKS_DATABASE

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", env_prefix="DIGESTIFY_API_"
    )

    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    email_backend: Literal["resend", "console"] = "resend"
    run_worker: bool = False
    worker_index: int = Field(default=0, ge=0, lt=256)
    worker_count: int = Field(default=1, ge=1, le=256)
    worker_concurrency: int = Field(default=10, ge=1)


class ConsoleEmailClient(EmailClient):
    """Local development only: sign-in codes are exposed in server logs."""

    def __init__(self) -> None:
        pass

    async def send(self, to: str, subject: str, text: str) -> None:
        logger.warning("Development email to %s: %s\n%s", to, subject, text)


@dataclass
class Services:
    client: Client
    tasks: TaskService
    news: NewsService


@asynccontextmanager
async def connect_services() -> AsyncIterator[Services]:
    async with Client.connect() as client:
        tasks = TaskService(client)
        news = NewsService(client, tasks)
        for attempt in range(5):
            try:
                await client.ensure_databases(
                    (IDENTITY_DATABASE, NEWS_DATABASE, TASKS_DATABASE)
                )
                await tasks.init()
                await news.init()
                break
            except (httpx.TransportError, httpx.HTTPStatusError) as error:
                if attempt == 4 or (
                    isinstance(error, httpx.HTTPStatusError)
                    and error.response.status_code
                    not in (409, 429, 500, 502, 503, 504)
                ):
                    raise
                logger.warning("Database initialization failed; retrying")
                await asyncio.sleep(2**attempt)
        yield Services(client, tasks, news)


def create_worker(services: Services, settings: Settings) -> Worker:
    return Worker(
        services.tasks,
        {TASK_KIND: services.news.run},
        partition=Partition(settings.worker_index, settings.worker_count),
        concurrency=settings.worker_concurrency,
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        options = settings or Settings()
        generator, verifier = TokenGenerator(), TokenVerifier()
        async with AsyncExitStack() as stack:
            services = await stack.enter_async_context(connect_services())
            email = (
                ConsoleEmailClient()
                if options.email_backend == "console"
                else await stack.enter_async_context(EmailClient.create())
            )
            app.state.identity_token_verifier = verifier
            app.state.identity_service = IdentityService(
                services.client,
                email,
                generator,
                verifier,
            )
            app.state.news_service = services.news
            worker_task = (
                asyncio.create_task(create_worker(services, options).run())
                if options.run_worker
                else None
            )
            try:
                yield
            finally:
                if worker_task is not None:
                    worker_task.cancel()
                    await asyncio.gather(worker_task, return_exceptions=True)

    app = FastAPI(title="Digestify API", lifespan=lifespan)
    app.include_router(identity_router)
    app.include_router(news_router)
    return app


async def run_worker(settings: Settings) -> None:
    async with connect_services() as services:
        await create_worker(services, settings).run()


def run_app() -> None:
    parser = argparse.ArgumentParser(description="Digestify API and workers")
    parser.add_argument(
        "command", choices=("serve", "worker"), default="serve", nargs="?"
    )
    arguments = parser.parse_args()
    settings = Settings()
    logging.basicConfig(level=logging.INFO)
    if arguments.command == "worker":
        asyncio.run(run_worker(settings))
    else:
        uvicorn.run(
            create_app(settings), host=settings.host, port=settings.port
        )


app = create_app()
