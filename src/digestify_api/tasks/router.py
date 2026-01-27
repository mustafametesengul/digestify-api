from types import FunctionType
from typing import Awaitable, Callable, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)
AsyncTaskHandler = Callable[[T], Awaitable[None]]


class TaskRouter:
    def __init__(self) -> None:
        self._handlers: dict[str, AsyncTaskHandler] = {}

    def register_handler(
        self,
        handler: AsyncTaskHandler,
    ) -> None:
        if not isinstance(handler, FunctionType):
            raise TypeError("Handler must be a function")
        self._handlers[handler.__name__] = handler

    def get_handler(self, name: str) -> AsyncTaskHandler | None:
        return self._handlers.get(name)
