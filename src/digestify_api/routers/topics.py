from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends

from digestify_api import dependencies, exceptions, models, queries

router = APIRouter(
    prefix="/topics",
    tags=["topics"],
)


@router.post("/create", status_code=201)
async def create(
    auth: Annotated[models.auth.Auth, Depends(dependencies.auth.get_auth)],
    db_manager: Annotated[
        dependencies.db.DBManager, Depends(dependencies.db.get_db_manager)
    ],
    payload: models.topics.CreateTopicRequest,
) -> models.topics.TopicResponse:
    if auth.is_anonymous:
        raise exceptions.auth.InsufficientPermissions()

    now = datetime.now(timezone.utc)

    openai = dependencies.openai.get_openai()

    openai_input = f"{payload.name}\n\n{payload.description}"
    flagged = await openai.check_for_moderation([openai_input])
    if flagged[0]:
        raise exceptions.topics.TopicContainsInappropriateContent()

    embeddings = await openai.get_embeddings([openai_input])
    embedding = embeddings[0]

    async with db_manager.get_connection() as connection:
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

        if user.created_topics_count >= 50:
            raise exceptions.topics.TopicLimitExceeded(
                detail=(
                    "You have reached the maximum number of created topics (50). "
                    "Please delete some topics to create new ones."
                )
            )

        if user.active_topics_count >= 5 and user.tier is models.users.UserTier.PREMIUM:
            raise exceptions.topics.TopicLimitExceeded(
                detail=(
                    "Premium tier users can have up to 5 active topics. "
                    "Please deactivate some topics to create new ones."
                )
            )

        await queries.users.increment_created_topics_count(connection, auth.id)
        await queries.users.increment_active_topics_count(connection, auth.id)

        topic = models.topics.Topic(
            id=uuid4(),
            user_id=auth.id,
            discarded=False,
            image_url=None,
            is_active=True,
            name=payload.name,
            description=payload.description,
            language=payload.language,
            followers_count=1,
            created_at=now,
            updated_at=None,
            embedding=embedding,
            schedule_time=payload.schedule_time,
            schedule_timezone=payload.schedule_timezone,
            schedule_version=1,
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

        task_payload = models.stories.FetchAndSaveStoriesTask(
            topic_id=topic.id,
            schedule_version=topic.schedule_version,
        )

        tz = ZoneInfo(payload.schedule_timezone)
        now_in_tz = datetime.now(tz)
        task_schedule = now_in_tz.replace(
            hour=payload.schedule_time.hour,
            minute=payload.schedule_time.minute,
            second=0,
            microsecond=0,
        )
        task_schedule += timedelta(days=1)

        task = models.tasks.Task(
            id=uuid4(),
            name="fetch_and_save_stories",
            status=models.tasks.TaskStatus.PENDING,
            created_at=now,
            updated_at=None,
            payload=task_payload.model_dump_json(),
            scheduled_at=task_schedule,
            error_message=None,
        )
        await queries.tasks.create(connection, task)
        return models.topics.TopicResponse.model_validate(topic)


@router.post("/change_schedule", status_code=200)
async def change_schedule(
    auth: Annotated[models.auth.Auth, Depends(dependencies.auth.get_auth)],
    db_manager: Annotated[
        dependencies.db.DBManager, Depends(dependencies.db.get_db_manager)
    ],
    payload: models.topics.ChangeTopicScheduleRequest,
) -> None:
    if auth.is_anonymous:
        raise exceptions.auth.InsufficientPermissions()

    now = datetime.now(timezone.utc)

    async with db_manager.get_connection() as connection:
        topic = await queries.topics.get(connection, payload.topic_id, lock=True)
        if topic is None or topic.user_id != auth.id:
            raise exceptions.topics.TopicNotFound()

        topic.schedule_time = payload.schedule_time
        topic.schedule_timezone = payload.schedule_timezone
        topic.schedule_version += 1
        topic.updated_at = now

        await queries.topics.update(connection, topic)

        task_payload = models.stories.FetchAndSaveStoriesTask(
            topic_id=topic.id,
            schedule_version=topic.schedule_version,
        )

        tz = ZoneInfo(payload.schedule_timezone)
        now_in_tz = datetime.now(tz)
        task_schedule = now_in_tz.replace(
            hour=payload.schedule_time.hour,
            minute=payload.schedule_time.minute,
            second=0,
            microsecond=0,
        )
        task_schedule += timedelta(days=1)

        task = models.tasks.Task(
            id=uuid4(),
            name="fetch_and_save_stories",
            status=models.tasks.TaskStatus.PENDING,
            created_at=now,
            updated_at=None,
            payload=task_payload.model_dump_json(),
            scheduled_at=task_schedule,
            error_message=None,
        )
        await queries.tasks.create(connection, task)


@router.get("/most_followed")
async def get_most_followed(
    auth: Annotated[models.auth.Auth, Depends(dependencies.auth.get_auth)],
    db_manager: Annotated[
        dependencies.db.DBManager, Depends(dependencies.db.get_db_manager)
    ],
    language: models.topics.Language,
) -> list[models.topics.TopicResponse]:
    async with db_manager.get_connection() as connection:
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
    db_manager: Annotated[
        dependencies.db.DBManager, Depends(dependencies.db.get_db_manager)
    ],
    query: str,
    language: models.topics.Language,
) -> list[models.topics.TopicResponse]:
    openai = dependencies.openai.get_openai()

    embeddings = await openai.get_embeddings([query])
    embedding = embeddings[0]

    async with db_manager.get_connection() as connection:
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


@router.post("/activate", status_code=200)
async def activate_topic(
    auth: Annotated[models.auth.Auth, Depends(dependencies.auth.get_auth)],
    db_manager: Annotated[
        dependencies.db.DBManager, Depends(dependencies.db.get_db_manager)
    ],
    topic_id: UUID,
) -> None:
    if auth.is_anonymous:
        raise exceptions.auth.InsufficientPermissions()

    now = datetime.now(timezone.utc)

    async with db_manager.get_connection() as connection:
        user = await queries.users.get(connection, auth.id, lock=True)
        if user is None:
            raise exceptions.users.UserNotFound()

        topic = await queries.topics.get(connection, topic_id, lock=True)
        if topic is None or topic.user_id != auth.id:
            raise exceptions.topics.TopicNotFound()

        if topic.is_active:
            return

        if user.active_topics_count >= 5 and user.tier is models.users.UserTier.PREMIUM:
            raise exceptions.topics.TopicLimitExceeded(
                detail=(
                    "Premium tier users can have up to 5 active topics. "
                    "Please deactivate some topics to activate new ones."
                )
            )

        topic.is_active = True
        topic.updated_at = now

        await queries.topics.update(connection, topic)
        await queries.users.increment_active_topics_count(connection, auth.id)


@router.post("/deactivate", status_code=200)
async def deactivate_topic(
    auth: Annotated[models.auth.Auth, Depends(dependencies.auth.get_auth)],
    db_manager: Annotated[
        dependencies.db.DBManager, Depends(dependencies.db.get_db_manager)
    ],
    topic_id: UUID,
) -> None:
    if auth.is_anonymous:
        raise exceptions.auth.InsufficientPermissions()

    now = datetime.now(timezone.utc)

    async with db_manager.get_connection() as connection:
        user = await queries.users.get(connection, auth.id, lock=True)
        if user is None:
            raise exceptions.users.UserNotFound()

        topic = await queries.topics.get(connection, topic_id, lock=True)
        if topic is None or topic.user_id != auth.id:
            raise exceptions.topics.TopicNotFound()

        if not topic.is_active:
            return

        topic.is_active = False
        topic.updated_at = now

        await queries.topics.update(connection, topic)
        await queries.users.decrement_active_topics_count(connection, auth.id)
