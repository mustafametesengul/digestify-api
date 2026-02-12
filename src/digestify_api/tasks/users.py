from datetime import datetime, timedelta, timezone
from uuid import uuid4

from digestify_api import dependencies, models, queries

task_registry = dependencies.tasks.TaskRegistry()


@task_registry.register
async def check_user_tier(task: models.tasks.Task) -> None:
    payload = models.users.CheckUserTierTask.model_validate_json(task.payload)
    db = dependencies.db.get_db_manager()

    async with db.get_connection() as connection:
        now = datetime.now(timezone.utc)
        user = await queries.users.get(connection, payload.user_id, lock=True)
        if user is None or user.discarded:
            await queries.tasks.mark_as_completed(connection, task.id, now)
            return

        if (
            user.tier is models.users.UserTier.PREMIUM
            and now - user.tier_last_confirmed_at > timedelta(days=35)
        ):
            user.tier = models.users.UserTier.FREE
            user.tier_last_confirmed_at = now
            user.updated_at = now
            await queries.users.update(connection, user)

            topics = await queries.topics.list_by_user_id(connection, user.id)
            for topic in topics:
                topic.is_active = False
                topic.updated_at = now
                await queries.topics.update(connection, topic)

        schedule_time = now + timedelta(days=5)

        new_task = models.tasks.Task(
            id=uuid4(),
            name=task.name,
            payload=task.payload,
            created_at=now,
            updated_at=None,
            scheduled_at=schedule_time,
            status=models.tasks.TaskStatus.PENDING,
            error_message=None,
        )
        await queries.tasks.create(connection, new_task)
        await queries.tasks.mark_as_completed(connection, task.id, now)
