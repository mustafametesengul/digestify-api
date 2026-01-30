import inspect
from dataclasses import dataclass
from datetime import datetime
from types import FunctionType
from typing import Awaitable, Callable, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel

from digestify_api.models.tasks import Task, TaskStatus

T = TypeVar("T", bound=BaseModel)
AsyncTaskHandler = Callable[[UUID, T], Awaitable[None]]


def from_handler(
    handler: AsyncTaskHandler[T],
    payload: T,
    created_at: datetime,
    task_id: UUID | None = None,
    scheduled_at: datetime | None = None,
) -> Task:
    if not isinstance(handler, FunctionType):
        raise ValueError("Handler must be a function")

    if scheduled_at is None:
        scheduled_at = created_at

    if task_id is None:
        task_id = uuid4()

    task = Task(
        id=task_id,
        name=handler.__name__,
        payload=payload.model_dump_json(),
        scheduled_at=scheduled_at,
        status=TaskStatus.PENDING,
        created_at=created_at,
        updated_at=None,
        error_message=None,
    )
    return task


@dataclass
class TaskDefinition:
    handler: AsyncTaskHandler
    model_class: type[BaseModel]


class TaskRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, TaskDefinition] = {}

    def task(
        self,
        handler: AsyncTaskHandler[T],
    ) -> AsyncTaskHandler[T]:
        if not isinstance(handler, FunctionType):
            raise TypeError("Handler must be a function")

        sig = inspect.signature(handler)
        params = list(sig.parameters.values())
        if len(params) != 1:
            raise ValueError("Handler must have exactly one argument")

        model_class = params[0].annotation
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
