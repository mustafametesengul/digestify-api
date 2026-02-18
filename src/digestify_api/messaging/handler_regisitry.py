import inspect
from dataclasses import dataclass
from types import FunctionType
from typing import Awaitable, Callable, TypeVar

from digestify_api.messaging.models import Command, Event, Message, Reply


@dataclass
class HandlerBinding:
    channel: str
    message_type: str
    handler_name: str
    handler: Callable[[Message], Awaitable[None]]


Handler = Callable[..., Awaitable[None]]
T_Handler = TypeVar("T_Handler", bound=Handler)


class HandlerRegistry:
    def __init__(self) -> None:
        self._handlers: list[HandlerBinding] = []

    def register(
        self,
        service: str,
    ) -> Callable[[T_Handler], T_Handler]:
        def decorator(handler: T_Handler) -> T_Handler:
            if not isinstance(handler, FunctionType):
                raise TypeError("Handler must be a function")

            sig = inspect.signature(handler)
            params = list(sig.parameters.values())
            if len(params) != 1:
                raise ValueError("Handler must have exactly one argument")

            arg_type = params[0].annotation
            if not (
                inspect.isclass(arg_type)
                and issubclass(arg_type, (Event, Command, Reply))
            ):
                raise TypeError(
                    "Handler argument must be a subclass of Event, Command, or Reply"
                )

            handler_name = handler.__name__
            message_type = arg_type.__name__

            already_exists = any(h.handler_name == handler_name for h in self._handlers)
            if issubclass(arg_type, Command) and already_exists:
                msg = f"Handler for command {message_type} already exists"
                raise ValueError(msg)

            if issubclass(arg_type, Reply) and already_exists:
                msg = f"Handler for reply {message_type} already exists"
                raise ValueError(msg)

            async def wrapper(message: Message) -> None:
                payload = arg_type.model_validate_json(message.payload)
                await handler(payload)

            handler_binding = HandlerBinding(
                channel=service,
                message_type=message_type,
                handler_name=handler_name,
                handler=wrapper,
            )

            self._handlers.append(handler_binding)

            return handler

        return decorator

    @property
    def handlers(self) -> list[HandlerBinding]:
        return self._handlers
