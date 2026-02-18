import inspect
from dataclasses import dataclass
from types import FunctionType
from typing import Awaitable, Callable

from digestify_api.messaging.models import Message


@dataclass
class HandlerBinding:
    stream: str
    message_type: str
    consumer_group: str
    handler: Callable[[Message], Awaitable[None]]


Handler = Callable[[Message], Awaitable[None]]


class HandlerRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, HandlerBinding] = {}

    def register(
        self,
        stream: str,
        message_type: str,
        consumer_group: str,
    ) -> Callable[[Handler], Handler]:
        def decorator(handler: Handler) -> Handler:
            if not isinstance(handler, FunctionType):
                raise TypeError("Handler must be a function")

            sig = inspect.signature(handler)
            params = list(sig.parameters.values())
            if len(params) != 1:
                raise ValueError("Handler must have exactly one argument")

            if params[0].annotation is not Message:
                raise TypeError("Handler argument must be of type Message")

            self._handlers[stream] = HandlerBinding(
                stream=stream,
                message_type=message_type,
                consumer_group=consumer_group,
                handler=handler,
            )
            return handler

        return decorator

    def get_handler(self, name: str) -> Handler | None:
        handler_info = self._handlers.get(name)
        return handler_info.handler if handler_info else None
