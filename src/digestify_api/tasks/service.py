import asyncio
from datetime import datetime, timezone

from pydantic import BaseModel

from digestify_api.db import DBService
from digestify_api.tasks.models import Task, TaskStatus
from digestify_api.tasks.repository import TaskRepository
from digestify_api.tasks.router import AsyncTaskHandler, TaskRouter


class TaskService:
    def __init__(self, db: DBService) -> None:
        self._routers: list[TaskRouter] = []
        self._queue: asyncio.Queue[Task] = asyncio.Queue()
        self._db = db
        self._tasks: list[asyncio.Task] = []

    def add_router(self, router: TaskRouter) -> None:
        self._routers.append(router)

    async def _queue_pending_tasks(self) -> None:
        while True:
            now = datetime.now(timezone.utc)
            async with self._db.get_connection() as connection:
                task_repository = TaskRepository(connection)
                pending_tasks = await task_repository.get_pending_tasks()
                for task in pending_tasks:
                    await self._queue.put(task)
                    task.status = TaskStatus.IN_PROGRESS
                    task.updated_at = now
                    await task_repository.update_task(task)
            await asyncio.sleep(10)

    async def _handle_tasks(self) -> None:
        while True:
            task = await self._queue.get()

            handler: AsyncTaskHandler | None = None
            for router in self._routers:
                handler = router.get_handler(task.name)
                if handler is not None:
                    break

            if handler is None:
                print(f"No handler found for task name {task.name}")
                self._queue.task_done()
                continue

            payload = BaseModel.model_validate(task.payload)

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
                    task_repository = TaskRepository(connection)
                    task = await task_repository.read_task(
                        task.id,
                        lock=True,
                    )
                    if task is None:
                        raise ValueError("Task not found")

                    task.status = task_status
                    task.updated_at = datetime.now(timezone.utc)
                    task.error_message = error_message
                    await task_repository.update_task(task)

                self._queue.task_done()

    async def start(self) -> None:
        task = asyncio.create_task(self._handle_tasks())
        self._tasks.append(task)
        task = asyncio.create_task(self._queue_pending_tasks())
        self._tasks.append(task)
        await asyncio.gather(*self._tasks)

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
