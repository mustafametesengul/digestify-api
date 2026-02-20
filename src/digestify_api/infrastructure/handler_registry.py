import inspect
from dataclasses import dataclass
from types import FunctionType
from typing import Awaitable, Callable, TypeVar

from pydantic import BaseModel

from digestify_api.infrastructure.channel import Channel
from digestify_api.infrastructure.models import Command, Event, Message, Reply


@dataclass
class HandlerBinding:
    channel: Channel
    message_type: str
    handler_name: str
    handler: Callable[[Message], Awaitable[None]]


Handler = Callable[..., Awaitable[None]]
T_Handler = TypeVar("T_Handler", bound=Handler)


class HandlerRegistry:
    def __init__(self, channel: Channel) -> None:
        self._handlers: list[HandlerBinding] = []
        self._channel = channel

    def _register(
        self,
        handler: T_Handler,
        allowed_type: type,
        channel: Channel | None = None,
        check_duplicates: bool = True,
    ) -> T_Handler:
        if not isinstance(handler, FunctionType):
            raise TypeError("Handler must be a function")

        sig = inspect.signature(handler)
        params = list(sig.parameters.values())
        if len(params) != 1:
            raise ValueError("Handler must have exactly one argument")

        arg_type = params[0].annotation
        if not (
            inspect.isclass(arg_type)
            and issubclass(arg_type, allowed_type)
            and issubclass(arg_type, BaseModel)
        ):
            msg = f"Handler argument must be a subclass of {allowed_type.__name__}"
            raise TypeError(msg)

        handler_name = handler.__name__
        message_type = arg_type.__name__

        if channel is None:
            channel = self._channel

        if check_duplicates:
            already_exists = any(
                h.message_type == message_type and h.channel == channel
                for h in self._handlers
            )
            if already_exists:
                msg = f"Handler for {message_type} on channel {channel} already exists"
                raise ValueError(msg)

        async def wrapper(message: Message) -> None:
            payload = arg_type.model_validate_json(message.payload)
            await handler(payload)

        handler_binding = HandlerBinding(
            channel=channel,
            message_type=message_type,
            handler_name=handler_name,
            handler=wrapper,
        )

        self._handlers.append(handler_binding)
        return handler

    def event(self, channel: Channel) -> Callable[[T_Handler], T_Handler]:
        def decorator(handler: T_Handler) -> T_Handler:
            return self._register(
                handler,
                channel=channel,
                allowed_type=Event,
                check_duplicates=False,
            )

        return decorator

    def command(self) -> Callable[[T_Handler], T_Handler]:
        def decorator(handler: T_Handler) -> T_Handler:
            return self._register(handler=handler, allowed_type=Command)

        return decorator

    def reply(self) -> Callable[[T_Handler], T_Handler]:
        def decorator(handler: T_Handler) -> T_Handler:
            return self._register(handler=handler, allowed_type=Reply)

        return decorator

    @property
    def handlers(self) -> list[HandlerBinding]:
        return self._handlers
