from contextlib import asynccontextmanager
from typing import AsyncIterator

from digestify_api.infrastructure.database import create_client
from digestify_api.infrastructure.token_verification import TokenVerifier
from digestify_api.news.dependencies import Context
from digestify_api.news.models import Checkpoint, Story, Topic, User
from digestify_api.news.scheduler import TopicScheduler
from digestify_api.news.user_projection import UserProjection

DATABASE = "news"
IDENTITY_DATABASE = "identity"


@asynccontextmanager
async def lifespan() -> AsyncIterator[Context]:
    async with create_client() as client:
        await client.ensure_database(DATABASE)
        database = client.get_database(DATABASE, User, Topic, Story, Checkpoint)
        await database.ensure_index(
            name="documents-by-type",
            fields=["type"],
        )
        await database.ensure_index(
            name="stories-by-topic",
            fields=["type", "topic_id", "created_at"],
        )

        async for doc in database.changes():
            print(doc.doc)

        # projection = UserProjection(
        #     database,
        #     users,
        #     checkpoints,
        #     source_database=IDENTITY_DATABASE,
        # )
        # scheduler = TopicScheduler(topics, stories, quotas, active_topics)

        # tasks = [
        #     asyncio.create_task(projection.run()),
        #     asyncio.create_task(scheduler.run()),
        # ]

        try:
            yield Context(
                database=database,
                token_verifier=TokenVerifier(),
            )
        finally:
            pass
            # for task in tasks:
            #     task.cancel()
            # for task in tasks:
            #     with suppress(asyncio.CancelledError):
            #         await task
