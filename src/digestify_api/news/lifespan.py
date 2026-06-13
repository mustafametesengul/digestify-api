import asyncio
from contextlib import asynccontextmanager, suppress
from typing import AsyncIterator

import httpx

from digestify_api.infrastructure.couchdb import (
    CouchDBRepository,
    CouchDBSettings,
    ensure_database,
)
from digestify_api.infrastructure.token_verification import TokenVerifier
from digestify_api.news.checkpoint import ProjectionCheckpoint
from digestify_api.news.dependencies import Context
from digestify_api.news.user import User
from digestify_api.news.user_projection import UserProjection

DATABASE = "news"
IDENTITY_DATABASE = "identity"


@asynccontextmanager
async def lifespan() -> AsyncIterator[Context]:
    settings = CouchDBSettings()

    async with httpx.AsyncClient(
        base_url=settings.url,
        auth=(settings.user, settings.password.get_secret_value()),
        timeout=httpx.Timeout(connect=10.0, read=None, write=10.0, pool=10.0),
    ) as couch_client:
        await ensure_database(couch_client, DATABASE)

        users = CouchDBRepository(couch_client, DATABASE, User)
        checkpoints = CouchDBRepository(couch_client, DATABASE, ProjectionCheckpoint)

        projection = UserProjection(
            couch_client,
            users,
            checkpoints,
            source_database=IDENTITY_DATABASE,
        )
        projection_task = asyncio.create_task(projection.run())

        try:
            yield Context(users=users, token_verifier=TokenVerifier())
        finally:
            projection_task.cancel()
            with suppress(asyncio.CancelledError):
                await projection_task
