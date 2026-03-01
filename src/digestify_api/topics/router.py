from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends

from digestify_api import identity, infrastructure
from digestify_api.topics import dependencies, exceptions, queries, schemas

router = APIRouter()


def _get_scheduled_at(schedule: datetime, now: datetime) -> datetime:
    return max(schedule - timedelta(minutes=10), now)


@router.post("/create", status_code=201)
async def create(
    auth: Annotated[identity.UserClaims, Depends(identity.get_user_claims)],
    database: Annotated[infrastructure.Database, Depends(dependencies.get_database)],
    payload: schemas.CreateTopic,
) -> schemas.TopicPublic:
    if auth.is_anonymous:
        raise identity.InsufficientPermissions()

    async with database.transaction() as connection:
        now = datetime.now(timezone.utc)

        user = await queries.get_user(connection, auth.id, lock=True)
        if user is None:
            raise exceptions.users.UserNotFound()

        if user.tier is schemas.users.UserTier.FREE:
            raise exceptions.TopicLimitExceeded(
                detail=(
                    "Free tier users cannot create topics. "
                    "Please upgrade your subscription to create topics."
                )
            )

        if user.created_topics_count >= 50:
            raise exceptions.TopicLimitExceeded(
                detail=(
                    "You have reached the maximum number of created topics (50). "
                    "Please delete some topics to create new ones."
                )
            )

        if (
            user.active_topics_count >= 5
            and user.tier is schemas.users.UserTier.PREMIUM
        ):
            raise exceptions.TopicLimitExceeded(
                detail=(
                    "Premium tier users can have up to 5 active topics. "
                    "Please deactivate some topics to create new ones."
                )
            )

        daily_created_count = await queries.topics.count_created_since(
            connection, auth.id, now - timedelta(days=1)
        )
        if daily_created_count >= 5:
            raise exceptions.TopicLimitExceeded(
                detail=(
                    "You have reached the daily limit of created topics (5). "
                    "Please try again later."
                )
            )

        await queries.users.increment_created_topics_count(connection, auth.id)
        await queries.users.increment_active_topics_count(connection, auth.id)

        tz = ZoneInfo(payload.schedule_timezone)
        now_in_tz = now.astimezone(tz)
        if payload.schedule_time < now_in_tz.time():
            schedule_date = now_in_tz.date() + timedelta(days=1)
        else:
            schedule_date = now_in_tz.date()
        schedule = datetime.combine(schedule_date, payload.schedule_time, tzinfo=tz)

        topic = schemas.topics.Topic(
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
            schedule_date=schedule_date,
        )

        await queries.topics.create(connection, topic)

        follow = schemas.follows.Follow(
            user_id=auth.id,
            topic_id=topic.id,
            is_following=True,
            created_at=now,
            updated_at=None,
        )

        await queries.follows.create(connection, follow)

        task_payload = schemas.stories.FetchAndSaveStoriesTask(
            topic_id=topic.id,
            schedule_version=topic.schedule_version,
            schedule_date=topic.schedule_date,
            schedule_time=topic.schedule_time,
            schedule_timezone=topic.schedule_timezone,
        )

        task = schemas.tasks.Task(
            id=uuid4(),
            name="fetch_and_save_stories",
            status=schemas.tasks.TaskStatus.PENDING,
            created_at=now,
            updated_at=None,
            payload=task_payload.model_dump_json(),
            scheduled_at=_get_scheduled_at(schedule, now),
            error_message=None,
        )
        await queries.tasks.create(connection, task)
        return schemas.topics.TopicResponse.model_validate(topic)


@router.post("/change_schedule", status_code=200)
async def change_schedule(
    auth: Annotated[schemas.auth.Auth, Depends(dependencies.auth.get_auth)],
    db_manager: Annotated[
        dependencies.db.DBManager, Depends(dependencies.db.get_db_manager)
    ],
    payload: schemas.topics.ChangeTopicScheduleRequest,
) -> None:
    if auth.is_anonymous:
        raise exceptions.auth.InsufficientPermissions()

    async with db_manager.get_connection() as connection:
        now = datetime.now(timezone.utc)

        topic = await queries.topics.get(connection, payload.topic_id, lock=True)
        if topic is None or topic.user_id != auth.id:
            raise exceptions.topics.TopicNotFound()

        tz = ZoneInfo(payload.schedule_timezone)
        now_in_tz = now.astimezone(tz)
        if payload.schedule_time < now_in_tz.time():
            schedule_date = now_in_tz.date() + timedelta(days=1)
        else:
            schedule_date = now_in_tz.date()
        schedule_date = max(schedule_date, topic.schedule_date)
        schedule = datetime.combine(schedule_date, payload.schedule_time, tzinfo=tz)

        topic.schedule_time = payload.schedule_time
        topic.schedule_timezone = payload.schedule_timezone
        topic.schedule_version += 1
        topic.updated_at = now
        topic.schedule_date = schedule_date

        await queries.topics.update(connection, topic)

        task_payload = schemas.stories.FetchAndSaveStoriesTask(
            topic_id=topic.id,
            schedule_version=topic.schedule_version,
            schedule_date=topic.schedule_date,
            schedule_time=topic.schedule_time,
            schedule_timezone=topic.schedule_timezone,
        )

        task = schemas.tasks.Task(
            id=uuid4(),
            name="fetch_and_save_stories",
            status=schemas.tasks.TaskStatus.PENDING,
            created_at=now,
            updated_at=None,
            payload=task_payload.model_dump_json(),
            scheduled_at=_get_scheduled_at(schedule, now),
            error_message=None,
        )
        await queries.tasks.create(connection, task)


@router.post("/activate", status_code=200)
async def activate_topic(
    auth: Annotated[schemas.auth.Auth, Depends(dependencies.auth.get_auth)],
    db_manager: Annotated[
        dependencies.db.DBManager, Depends(dependencies.db.get_db_manager)
    ],
    topic_id: UUID,
) -> None:
    if auth.is_anonymous:
        raise exceptions.auth.InsufficientPermissions()

    async with db_manager.get_connection() as connection:
        now = datetime.now(timezone.utc)

        user = await queries.users.get(connection, auth.id, lock=True)
        if user is None:
            raise exceptions.users.UserNotFound()

        topic = await queries.topics.get(connection, topic_id, lock=True)
        if topic is None or topic.user_id != auth.id:
            raise exceptions.topics.TopicNotFound()

        if topic.is_active:
            return

        if user.tier is schemas.users.UserTier.FREE:
            raise exceptions.topics.TopicLimitExceeded(
                detail=(
                    "Free tier users cannot activate topics. "
                    "Please upgrade your subscription to activate topics."
                )
            )

        if (
            user.active_topics_count >= 5
            and user.tier is schemas.users.UserTier.PREMIUM
        ):
            raise exceptions.topics.TopicLimitExceeded(
                detail=(
                    "Premium tier users can have up to 5 active topics. "
                    "Please deactivate some topics to activate new ones."
                )
            )

        tz = ZoneInfo(topic.schedule_timezone)
        now_in_tz = now.astimezone(tz)
        if topic.schedule_time < now_in_tz.time():
            schedule_date = now_in_tz.date() + timedelta(days=1)
        else:
            schedule_date = now_in_tz.date()
        schedule_date = max(schedule_date, topic.schedule_date)
        schedule = datetime.combine(schedule_date, topic.schedule_time, tzinfo=tz)

        topic.is_active = True
        topic.updated_at = now
        topic.schedule_version += 1
        topic.schedule_date = schedule_date

        await queries.topics.update(connection, topic)
        await queries.users.increment_active_topics_count(connection, auth.id)

        task_paylaod = schemas.stories.FetchAndSaveStoriesTask(
            topic_id=topic.id,
            schedule_version=topic.schedule_version,
            schedule_date=topic.schedule_date,
            schedule_time=topic.schedule_time,
            schedule_timezone=topic.schedule_timezone,
        )
        task = schemas.tasks.Task(
            id=uuid4(),
            name="fetch_and_save_stories",
            status=schemas.tasks.TaskStatus.PENDING,
            created_at=now,
            updated_at=None,
            payload=task_paylaod.model_dump_json(),
            scheduled_at=_get_scheduled_at(schedule, now),
            error_message=None,
        )
        await queries.tasks.create(connection, task)


@router.post("/deactivate", status_code=200)
async def deactivate_topic(
    auth: Annotated[schemas.auth.Auth, Depends(dependencies.auth.get_auth)],
    db_manager: Annotated[
        dependencies.db.DBManager, Depends(dependencies.db.get_db_manager)
    ],
    topic_id: UUID,
) -> None:
    if auth.is_anonymous:
        raise exceptions.auth.InsufficientPermissions()

    async with db_manager.get_connection() as connection:
        now = datetime.now(timezone.utc)

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


@router.get("/most_followed")
async def get_most_followed(
    auth: Annotated[schemas.auth.Auth, Depends(dependencies.auth.get_auth)],
    db_manager: Annotated[
        dependencies.db.DBManager, Depends(dependencies.db.get_db_manager)
    ],
    language: schemas.topics.Language,
) -> list[schemas.topics.TopicResponse]:
    async with db_manager.get_connection() as connection:
        topics = await queries.topics.get_most_followed(
            connection,
            language=language,
            limit=20,
        )
        topics_public = [
            schemas.topics.TopicResponse.model_validate(topic) for topic in topics
        ]
        return topics_public
