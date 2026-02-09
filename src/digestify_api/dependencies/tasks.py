import asyncio
import inspect
import logging
from datetime import datetime, timezone
from types import FunctionType
from typing import Awaitable, Callable

from digestify_api import models, queries
from digestify_api.dependencies import db

AsyncTaskHandler = Callable[[models.tasks.Task], Awaitable[None]]


_logger = logging.getLogger(__name__)


class TaskRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, AsyncTaskHandler] = {}

    def register(
        self,
        handler: AsyncTaskHandler,
    ) -> AsyncTaskHandler:
        if not isinstance(handler, FunctionType):
            raise TypeError("Handler must be a function")

        sig = inspect.signature(handler)
        params = list(sig.parameters.values())
        if len(params) != 1:
            raise ValueError("Handler must have exactly one argument")

        if params[0].annotation is not models.tasks.Task:
            raise TypeError("Handler argument must be of type Task")

        self._definitions[handler.__name__] = handler
        return handler

    def get_handler(self, name: str) -> AsyncTaskHandler | None:
        return self._definitions.get(name)


class TaskProcessor:
    def __init__(self, db: db.DBManager) -> None:
        self._db = db
        self._registries: list[TaskRegistry] = []
        self._queue: asyncio.Queue[models.tasks.Task] = asyncio.Queue()
        self._tasks: list[asyncio.Task] = []

    def add_registry(self, registry: TaskRegistry) -> None:
        self._registries.append(registry)

    async def _queue_pending_tasks(self) -> None:
        while True:
            now = datetime.now(timezone.utc)
            async with self._db.get_connection() as connection:
                pending_tasks = await queries.tasks.get_pending(
                    connection,
                    now,
                    limit=10,
                )
                _logger.debug(f"Found {len(pending_tasks)} pending tasks")
                for task in pending_tasks:
                    await self._queue.put(task)
                    await queries.tasks.mark_as_in_progress(connection, task.id, now)
            await asyncio.sleep(10)

    async def _handle_tasks(self) -> None:
        while True:
            task = await self._queue.get()

            handler = None
            for registry in self._registries:
                handler = registry.get_handler(task.name)
                if handler is not None:
                    break

            if handler is None:
                self._queue.task_done()
                continue

            try:
                _logger.info(f"Processing task {task.id} of type {task.name}")
                await handler(task)
                _logger.info(f"Completed task {task.id} of type {task.name}")
            except Exception as e:
                _logger.exception(
                    f"Error processing task {task.id} of type {task.name}: {e}"
                )
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
