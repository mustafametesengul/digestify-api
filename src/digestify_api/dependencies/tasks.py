import asyncio
import inspect
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from types import FunctionType
from typing import Awaitable, Callable, TypeVar
from uuid import UUID

from pydantic import BaseModel

from digestify_api import models, queries
from digestify_api.dependencies import db

T = TypeVar("T", bound=BaseModel)
AsyncTaskHandler = Callable[[UUID, T], Awaitable[None]]


_logger = logging.getLogger(__name__)


@dataclass
class TaskDefinition:
    handler: AsyncTaskHandler
    model_class: type[BaseModel]


class TaskRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, TaskDefinition] = {}

    def register(
        self,
        handler: AsyncTaskHandler[T],
    ) -> AsyncTaskHandler[T]:
        if not isinstance(handler, FunctionType):
            raise TypeError("Handler must be a function")

        sig = inspect.signature(handler)
        params = list(sig.parameters.values())
        if len(params) != 2:
            raise ValueError("Handler must have exactly two arguments")

        if params[0].annotation is not UUID:
            raise TypeError("First handler argument must be of type UUID")

        model_class = params[1].annotation
        if not issubclass(model_class, BaseModel):
            raise TypeError("Handler argument must be a Pydantic model")

        self._definitions[handler.__name__] = TaskDefinition(
            handler=handler, model_class=model_class
        )
        return handler

    def get_definition(self, name: str) -> TaskDefinition | None:
        return self._definitions.get(name)

    def get_handler(self, name: str) -> AsyncTaskHandler | None:
        definition = self.get_definition(name)
        return definition.handler if definition else None


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
                _logger.info(f"Processing task {task.id} of type {task.name}")
                await handler(task.id, payload)
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
