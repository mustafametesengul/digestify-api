import inspect
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

from pydantic import BaseModel

from digestify_api.infrastructure.channel import Channel


class Operation(BaseModel):
    channel: Channel
    name: str
    message_type: str


@dataclass
class OperationBinding:
    operation: Operation
    callable: Callable[..., Any]


F = TypeVar("F", bound=Callable[..., Any])


class MessageRouter:
    def __init__(self) -> None:
        self._operations: list[OperationBinding] = []
        self._events = Channel()
        self._commands = Channel()
        self._replies = Channel()

    @property
    def events(self) -> Channel:
        return self._events

    @property
    def commands(self) -> Channel:
        return self._commands

    @property
    def replies(self) -> Channel:
        return self._replies

    def set_name(self, name: str) -> None:
        self._events.address = f"{name}:events"
        self._commands.address = f"{name}:commands"
        self._replies.address = f"{name}:replies"

    def receive(
        self,
        channel: Channel,
        check_duplicates: bool = True,
    ) -> Callable[[F], F]:
        def decorator(operation: F) -> F:
            sig = inspect.signature(operation)
            params = list(sig.parameters.values())

            message_type_cls = None
            for param in params:
                if inspect.isclass(param.annotation) and issubclass(
                    param.annotation, BaseModel
                ):
                    message_type_cls = param.annotation
                    break

            if message_type_cls is None:
                msg = (
                    "Operation must have at least one argument that is a "
                    "subclass of BaseModel"
                )
                raise TypeError(msg)

            operation_name = operation.__name__
            message_type = message_type_cls.__name__

            if check_duplicates:
                already_exists = any(
                    o.operation.message_type == message_type
                    and o.operation.channel == channel
                    for o in self._operations
                )
                if already_exists:
                    msg = (
                        f"Operation for {message_type} on channel "
                        f"{channel} already exists"
                    )
                    raise ValueError(msg)

            operation_binding = OperationBinding(
                operation=Operation(
                    channel=channel,
                    name=operation_name,
                    message_type=message_type,
                ),
                callable=operation,
            )

            self._operations.append(operation_binding)
            return operation

        return decorator

    @property
    def operations(self) -> list[OperationBinding]:
        return self._operations
