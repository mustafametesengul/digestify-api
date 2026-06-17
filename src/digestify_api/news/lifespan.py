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
from digestify_api.news.active_topics import ActiveTopics
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
    # The scheduler's per-tick scan of every user's active-topic set. The topics
    # those sets reference are then loaded by `_id`, which uses CouchDB's
    # built-in primary index and so needs no Mango index of its own.
    await ensure_index(
        client,
        DATABASE,
        fields=["type"],
        name="documents-by-type",
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
        active_topics = CouchDBRepository(couch_client, DATABASE, ActiveTopics)
        checkpoints = CouchDBRepository(couch_client, DATABASE, ProjectionCheckpoint)

        projection = UserProjection(
            couch_client,
            users,
            checkpoints,
            source_database=IDENTITY_DATABASE,
        )
        scheduler = TopicScheduler(topics, stories, quotas, active_topics)

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
                active_topics=active_topics,
                token_verifier=TokenVerifier(),
            )
        finally:
            for task in tasks:
                task.cancel()
            for task in tasks:
                with suppress(asyncio.CancelledError):
                    await task
