from datetime import datetime, timezone
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends

from digestify_api import dependencies, exceptions, models, queries

router = APIRouter(
    prefix="/topics",
    tags=["topics"],
)


@router.post("/create", status_code=201)
async def create(
    auth: Annotated[models.auth.Auth, Depends(dependencies.auth.get_auth)],
    db: Annotated[dependencies.db.DBManager, Depends(dependencies.db.get_db_manager)],
    request: models.topics.CreateTopicRequest,
) -> models.topics.TopicResponse:
    now = datetime.now(timezone.utc)

    openai = dependencies.openai.get_openai()

    openai_input = f"{request.name}\n\n{request.description}"

    flagged = await openai.check_for_moderation([openai_input])

    if flagged[0]:
        raise exceptions.topics.TopicContainsInappropriateContent()

    embeddings = await openai.get_embeddings([openai_input])
    embedding = embeddings[0]

    async with db.get_connection() as connection:
        user = await queries.users.get(connection, auth.id, lock=True)
        if user is None:
            raise exceptions.users.UserNotFound()

        if user.tier is models.users.UserTier.FREE:
            raise exceptions.topics.TopicLimitExceeded(
                detail=(
                    "Free tier users cannot create topics. "
                    "Please upgrade your subscription to create topics."
                )
            )

        if (
            user.created_topics_count >= 5
            and user.tier is models.users.UserTier.PREMIUM
        ):
            raise exceptions.topics.TopicLimitExceeded(
                detail=(
                    "Premium tier users can create up to 5 topics. "
                    "Please delete some topics to create new ones."
                )
            )

        await queries.users.increment_created_topics_count(connection, auth.id)

        topic = models.topics.Topic(
            id=uuid4(),
            user_id=auth.id,
            discarded=False,
            image_url=None,
            is_active=True,
            name=request.name,
            description=request.description,
            language=request.language,
            followers_count=1,
            created_at=now,
            updated_at=None,
            embedding=embedding,
        )

        await queries.topics.create(connection, topic)

        follow = models.follows.Follow(
            user_id=auth.id,
            topic_id=topic.id,
            is_following=True,
            created_at=now,
            updated_at=None,
        )

        await queries.follows.create(connection, follow)

        payload = models.stories.StoryTaskPayload(topic_id=topic.id)

        task = models.tasks.Task(
            id=uuid4(),
            name="save_stories_by_topic",
            status=models.tasks.TaskStatus.PENDING,
            created_at=now,
            updated_at=None,
            payload=payload.model_dump_json(),
            scheduled_at=now,
            error_message=None,
        )
        await queries.tasks.create(connection, task)
        return models.topics.TopicResponse.model_validate(topic)


@router.get("/explore")
async def explore(
    auth: Annotated[models.auth.Auth, Depends(dependencies.auth.get_auth)],
    db: Annotated[dependencies.db.DBManager, Depends(dependencies.db.get_db_manager)],
    language: models.topics.Language,
) -> list[models.topics.TopicResponse]:
    async with db.get_connection() as connection:
        topics = await queries.topics.get_most_followed(
            connection,
            language=language,
            limit=20,
        )
        topics_public = [
            models.topics.TopicResponse.model_validate(topic) for topic in topics
        ]
        return topics_public


@router.get("/search")
async def search(
    auth: Annotated[models.auth.Auth, Depends(dependencies.auth.get_auth)],
    db: Annotated[dependencies.db.DBManager, Depends(dependencies.db.get_db_manager)],
    query: str,
    language: models.topics.Language,
) -> list[models.topics.TopicResponse]:
    openai = dependencies.openai.get_openai()

    embeddings = await openai.get_embeddings([query])
    embedding = embeddings[0]

    async with db.get_connection() as connection:
        topics = await queries.topics.get_by_embedding(
            connection,
            embedding=embedding,
            language=language,
            limit=20,
        )
        topics_public = [
            models.topics.TopicResponse.model_validate(topic) for topic in topics
        ]
        return topics_public
