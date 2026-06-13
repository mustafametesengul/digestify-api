import asyncio
from contextlib import asynccontextmanager, suppress
from typing import AsyncIterator

import httpx

from digestify_api.infrastructure.couchdb import (
    CouchDBRepository,
    CouchDBSettings,
    ensure_database,
    ensure_index,
)
from digestify_api.infrastructure.token_verification import TokenVerifier
from digestify_api.news.checkpoint import ProjectionCheckpoint
from digestify_api.news.dependencies import Context
from digestify_api.news.quota import FetchQuota
from digestify_api.news.scheduler import TopicScheduler
from digestify_api.news.story import Story
from digestify_api.news.topic import Topic
from digestify_api.news.user import User
from digestify_api.news.user_projection import UserProjection

DATABASE = "news"
IDENTITY_DATABASE = "identity"


async def _ensure_indexes(client: httpx.AsyncClient) -> None:
    # Listing/counting a user's topics, and checking the active-topic cap.
    await ensure_index(
        client,
        DATABASE,
        fields=["type", "user_id", "is_active"],
        name="topics-by-user",
    )
    # The scheduler's per-tick scan of all active topics.
    await ensure_index(
        client,
        DATABASE,
        fields=["type", "is_active"],
        name="topics-active",
    )
    # Latest-first stories for a topic.
    await ensure_index(
        client,
        DATABASE,
        fields=["type", "topic_id", "created_at"],
        name="stories-by-topic",
    )


@asynccontextmanager
async def lifespan() -> AsyncIterator[Context]:
    settings = CouchDBSettings()

    async with httpx.AsyncClient(
        base_url=settings.url,
        auth=(settings.user, settings.password.get_secret_value()),
        timeout=httpx.Timeout(connect=10.0, read=None, write=10.0, pool=10.0),
    ) as couch_client:
        await ensure_database(couch_client, DATABASE)
        await _ensure_indexes(couch_client)

        users = CouchDBRepository(couch_client, DATABASE, User)
        topics = CouchDBRepository(couch_client, DATABASE, Topic)
        stories = CouchDBRepository(couch_client, DATABASE, Story)
        quotas = CouchDBRepository(couch_client, DATABASE, FetchQuota)
        checkpoints = CouchDBRepository(couch_client, DATABASE, ProjectionCheckpoint)

        projection = UserProjection(
            couch_client,
            users,
            checkpoints,
            source_database=IDENTITY_DATABASE,
        )
        scheduler = TopicScheduler(topics, stories, quotas)

        tasks = [
            asyncio.create_task(projection.run()),
            asyncio.create_task(scheduler.run()),
        ]

        try:
            yield Context(
                users=users,
                topics=topics,
                stories=stories,
                quotas=quotas,
                token_verifier=TokenVerifier(),
            )
        finally:
            for task in tasks:
                task.cancel()
            for task in tasks:
                with suppress(asyncio.CancelledError):
                    await task
