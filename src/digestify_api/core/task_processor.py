import asyncio
from datetime import datetime, timezone

from digestify_api.core.db_manager import DBManager
from digestify_api.core.task_registry import TaskRegistry
from digestify_api.models import Task
from digestify_api.queries import get_pending_tasks, mark_task_in_progress


class TaskProcessor:
    def __init__(self, db: DBManager) -> None:
        self._db = db
        self._registries: list[TaskRegistry] = []
        self._queue: asyncio.Queue[Task] = asyncio.Queue()
        self._tasks: list[asyncio.Task] = []

    def add_registry(self, registry: TaskRegistry) -> None:
        self._registries.append(registry)

    async def _queue_pending_tasks(self) -> None:
        while True:
            now = datetime.now(timezone.utc)
            async with self._db.get_connection() as connection:
                pending_tasks = await get_pending_tasks(
                    connection,
                    now,
                    limit=10,
                )
                for task in pending_tasks:
                    await self._queue.put(task)
                    await mark_task_in_progress(connection, task.id, now)
            await asyncio.sleep(10)

    async def _handle_tasks(self) -> None:
        while True:
            task = await self._queue.get()

            definition = None
            for registry in self._registries:
                definition = registry.get_definition(task.name)
                if definition is not None:
                    break

            if definition is None:
                self._queue.task_done()
                continue

            model_type = definition.model_class
            payload = model_type.model_validate_json(task.payload)
            handler = definition.handler

            try:
                await handler(task.id, payload)
            finally:
                self._queue.task_done()

    async def start(self) -> None:
        task = asyncio.create_task(self._handle_tasks())
        self._tasks.append(task)
        task = asyncio.create_task(self._queue_pending_tasks())
        self._tasks.append(task)

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
