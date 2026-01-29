import asyncio
from datetime import datetime, timezone

from digestify_api.db import DBService
from digestify_api.queries.task_queries import (
    Task,
    TaskStatus,
    get_pending_tasks,
    read_task,
    update_task,
)
from digestify_api.task_processor.registry import TaskRegistry


class TaskProcessor:
    def __init__(self, db: DBService) -> None:
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
                pending_tasks = await get_pending_tasks(connection, now)
                for task in pending_tasks:
                    await self._queue.put(task)
                    task.status = TaskStatus.IN_PROGRESS
                    task.updated_at = now
                    await update_task(connection, task)
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
                print(f"No handler found for task name {task.name}")
                self._queue.task_done()
                continue

            model_type = definition.model_class
            payload = model_type.model_validate_json(task.payload)
            handler = definition.handler

            try:
                await handler(payload)
                task_status = TaskStatus.COMPLETED
                error_message = None
            except Exception as e:
                print(f"Error handling task {task.id}: {e}")
                task_status = TaskStatus.FAILED
                error_message = str(e)
            finally:
                async with self._db.get_connection() as connection:
                    task = await read_task(connection, task.id, lock=True)
                    if task is None:
                        raise ValueError("Task not found")

                    task.status = task_status
                    task.updated_at = datetime.now(timezone.utc)
                    task.error_message = error_message
                    await update_task(connection, task)

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
