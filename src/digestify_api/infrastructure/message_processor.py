import asyncio
import inspect
from logging import getLogger
from uuid import uuid4

from pydantic import BaseModel

from digestify_api.infrastructure.message_broker import MessageBroker
from digestify_api.infrastructure.message_router import (
    MessageRouter,
    OperationBinding,
)

_logger = getLogger(__name__)


class MessageProcessor:
    def __init__(
        self,
        context: object,
        message_broker: MessageBroker,
        message_router: MessageRouter,
    ) -> None:
        self._context = context
        self._message_broker = message_broker
        self._message_router = message_router

    async def _consume_stream(self, handler_binding: OperationBinding) -> None:
        stream_name = handler_binding.operation.channel.address
        if not stream_name:
            raise ValueError("Channel address cannot be empty")
        group_name = handler_binding.operation.name
        consumer_name = uuid4().hex

        _logger.info(
            f"Starting consumer {consumer_name} for stream {stream_name} "
            f"and group {group_name}"
        )
        await self._message_broker.create_consumer_group(stream_name, group_name)

        sig = inspect.signature(handler_binding.callable)

        payload_param_name: str | None = None
        payload_param_type: type[BaseModel] | None = None
        context_param_name: str | None = None

        for param_name, param in sig.parameters.items():
            if isinstance(param.annotation, type) and issubclass(
                param.annotation, BaseModel
            ):
                payload_param_name = param_name
                payload_param_type = param.annotation
            elif isinstance(self._context, param.annotation):
                context_param_name = param_name
        if (
            payload_param_name is None
            or payload_param_type is None
            or context_param_name is None
        ):
            raise ValueError(
                f"Handler {handler_binding.callable} requires a BaseModel parameter "
                f"and a context parameter."
            )

        iteration = 0
        autoclaim_start_id = "0-0"
        while True:
            iteration += 1
            is_autoclaim = False
            messages = []

            # Check pending messages every 10 iterations
            if iteration % 10 == 0:
                (
                    autoclaim_start_id,
                    messages,
                ) = await self._message_broker.autoclaim_messages(
                    stream_name,
                    group_name,
                    consumer_name,
                    start_id=autoclaim_start_id,
                    count=1,
                )
                is_autoclaim = True

                await self._message_broker.delete_ghost_consumers(
                    stream_name,
                    group_name,
                )

            if not messages:
                # If we didn't autoclaim any messages, check for new messages
                messages = await self._message_broker.consume_stream(
                    stream_name, group_name, consumer_name, start_id=">"
                )
                is_autoclaim = False

            if not messages:
                continue

            stream, message_id, message = messages[0]

            if stream != stream_name:
                await self._message_broker.acknowledge_message(
                    stream_name, group_name, message_id
                )
                continue

            if message.type != handler_binding.operation.message_type:
                await self._message_broker.acknowledge_message(
                    stream_name, group_name, message_id
                )
                continue

            kwargs: dict[str, object] = {}
            if payload_param_name:
                payload = payload_param_type.model_validate_json(message.payload)
                kwargs[payload_param_name] = payload
            if context_param_name:
                kwargs[context_param_name] = self._context

            await handler_binding.callable(**kwargs)

            await self._message_broker.acknowledge_message(
                stream_name, group_name, message_id
            )
            if is_autoclaim:
                # If we successfully processed a pending message, check for more
                # pending messages
                iteration = 9

    async def _safe_consume_stream(self, handler_binding: OperationBinding) -> None:
        try:
            await self._consume_stream(handler_binding)
        except asyncio.CancelledError:
            raise
        except Exception:
            _logger.exception(
                f"Consumer task for {handler_binding.operation.name} crashed"
            )
            raise

    async def run(self) -> None:
        tasks: list[asyncio.Task[None]] = []
        for handler_binding in self._message_router.operations:
            task = asyncio.create_task(self._safe_consume_stream(handler_binding))
            tasks.append(task)
        await asyncio.gather(*tasks)
