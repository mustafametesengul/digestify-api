import inspect
from dataclasses import dataclass
from types import FunctionType
from typing import Awaitable, Callable

from pydantic import BaseModel

from digestify_api.infrastructure.channel import Channel
from digestify_api.infrastructure.message import Message


class Operation(BaseModel):
    channel: Channel
    name: str
    message_type: str


@dataclass
class OperationBinding:
    operation: Operation
    callable: Callable[[Message], Awaitable[None]]


type OperationCallable[T: BaseModel] = Callable[[T], Awaitable[None]]


class OperationRegistry:
    def __init__(self) -> None:
        self._operations: list[OperationBinding] = []

    def receive[T: BaseModel](
        self,
        channel: Channel,
        check_duplicates: bool = True,
    ) -> Callable[[OperationCallable[T]], OperationCallable[T]]:
        def decorator(operation: OperationCallable[T]) -> OperationCallable[T]:
            if not isinstance(operation, FunctionType):
                raise TypeError("Operation must be a function")

            sig = inspect.signature(operation)
            params = list(sig.parameters.values())
            if len(params) != 1:
                raise ValueError("Operation must have exactly one argument")

            arg_type = params[0].annotation
            if not (inspect.isclass(arg_type) and issubclass(arg_type, BaseModel)):
                msg = "Operation argument must be a subclass of BaseModel"
                raise TypeError(msg)

            operation_name = operation.__name__
            message_type = arg_type.__name__

            if check_duplicates:
                already_exists = any(
                    o.operation.message_type == message_type
                    and o.operation.channel == channel
                    for o in self._operations
                )
                if already_exists:
                    msg = f"Operation for {message_type} on channel {channel} already exists"
                    raise ValueError(msg)

            async def wrapper(message: Message) -> None:
                payload = arg_type.model_validate_json(message.payload)
                await operation(payload)

            operation_binding = OperationBinding(
                operation=Operation(
                    channel=channel,
                    name=operation_name,
                    message_type=message_type,
                ),
                callable=wrapper,
            )

            self._operations.append(operation_binding)
            return operation

        return decorator

    @property
    def operations(self) -> list[OperationBinding]:
        return self._operations
