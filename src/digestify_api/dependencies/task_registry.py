import inspect
from dataclasses import dataclass
from types import FunctionType
from typing import Awaitable, Callable, TypeVar
from uuid import UUID

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)
AsyncTaskHandler = Callable[[UUID, T], Awaitable[None]]


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
