from datetime import datetime, timezone
from digestify_api.tasks.models import Task
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, col
from digestify_api.tasks.schemas import TaskStatus


async def poll_tasks(self, session: AsyncSession, limit: int = 10) -> None:
    task_results = await session.exec(
        select(Task)
        .where(
            col(Task.scheduled_at) <= datetime.now(timezone.utc),
            col(Task.status) == TaskStatus.PENDING,
        )
        .order_by(col(Task.scheduled_at).asc())
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    tasks = task_results.all()

    for task in tasks:
        redis_message = Message(
            id=str(task.id),
            type=task.type,
            payload=task.payload,
        )
        await self._redis.xadd(
            self._stream, {"data": redis_message.model_dump_json()}
        )

    for task in tasks:
        task.status = TaskStatus.IN_PROGRESS
