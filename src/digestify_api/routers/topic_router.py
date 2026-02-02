from datetime import datetime, timezone
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends

from digestify_api.dependencies import auth_manager, db_manager, openai_client
from digestify_api.exceptions import topic_exceptions, users_exceptions
from digestify_api.models import (
    auth_models,
    follow_models,
    story_models,
    task_models,
    topic_models,
    user_models,
)
from digestify_api.queries import (
    follow_queries,
    task_queries,
    topic_queries,
    user_queries,
)

router = APIRouter(
    prefix="/topics",
    tags=["topics"],
)


@router.post("/create", status_code=201)
async def create(
    auth: Annotated[auth_models.Auth, Depends(auth_manager.get_auth)],
    db: Annotated[db_manager.DBManager, Depends(db_manager.get_db)],
    new_topic: topic_models.CreateTopicRequest,
) -> topic_models.TopicResponse:
    now = datetime.now(timezone.utc)

    openai = openai_client.get_openai()

    openai_input = f"{new_topic.name}\n\n{new_topic.description}"

    flagged = await openai.check_for_moderation([openai_input])

    if flagged[0]:
        raise topic_exceptions.TopicContainsInappropriateContent()

    embeddings = await openai.get_embeddings([openai_input])
    embedding = embeddings[0]

    async with db.get_connection() as connection:
        user = await user_queries.get(connection, auth.id, lock=True)
        if user is None:
            raise users_exceptions.UserNotFound()

        topic_exists_flag = await topic_queries.exists(connection, new_topic.id)
        if topic_exists_flag:
            raise topic_exceptions.TopicAlreadyExists()
        if user.tier is user_models.UserTier.FREE:
            raise topic_exceptions.TopicLimitExceeded(
                detail=(
                    "Free tier users cannot create topics. "
                    "Please upgrade your subscription to create topics."
                )
            )

        if user.created_topics_count >= 5 and user.tier is user_models.UserTier.PREMIUM:
            raise topic_exceptions.TopicLimitExceeded(
                detail=(
                    "Premium tier users can create up to 5 topics. "
                    "Please delete some topics to create new ones."
                )
            )

        await user_queries.increment_created_topics_count(connection, auth.id)

        topic = topic_models.Topic(
            id=new_topic.id,
            user_id=auth.id,
            discarded=False,
            image_url=None,
            is_active=True,
            name=new_topic.name,
            description=new_topic.description,
            language=new_topic.language,
            followers_count=1,
            created_at=now,
            updated_at=None,
            embedding=embedding,
        )

        await topic_queries.create(connection, topic)

        follow = follow_models.Follow(
            user_id=auth.id,
            topic_id=topic.id,
            is_following=True,
            created_at=now,
            updated_at=None,
        )

        await follow_queries.create(connection, follow)

        payload = story_models.StoryTaskPayload(topic_id=topic.id)

        task = task_models.Task(
            id=uuid4(),
            name="save_stories_by_topic",
            status=task_models.TaskStatus.PENDING,
            created_at=now,
            updated_at=None,
            payload=payload.model_dump_json(),
            scheduled_at=now,
            error_message=None,
        )
        await task_queries.create(connection, task)
        return topic_models.TopicResponse.model_validate(topic)


@router.get("/explore")
async def explore(
    auth: Annotated[auth_models.Auth, Depends(auth_manager.get_auth)],
    db: Annotated[db_manager.DBManager, Depends(db_manager.get_db)],
    language: topic_models.Language,
) -> list[topic_models.TopicResponse]:
    async with db.get_connection() as connection:
        topics = await topic_queries.get_most_followed(
            connection,
            language=language,
            limit=20,
        )
        topics_public = [
            topic_models.TopicResponse.model_validate(topic) for topic in topics
        ]
        return topics_public


@router.get("/search")
async def search(
    auth: Annotated[auth_models.Auth, Depends(auth_manager.get_auth)],
    db: Annotated[db_manager.DBManager, Depends(db_manager.get_db)],
    query: str,
    language: topic_models.Language,
) -> list[topic_models.TopicResponse]:
    openai = openai_client.get_openai()

    embeddings = await openai.get_embeddings([query])
    embedding = embeddings[0]

    async with db.get_connection() as connection:
        topics = await topic_queries.get_by_embedding(
            connection,
            embedding=embedding,
            language=language,
            limit=20,
        )
        topics_public = [
            topic_models.TopicResponse.model_validate(topic) for topic in topics
        ]
        return topics_public
