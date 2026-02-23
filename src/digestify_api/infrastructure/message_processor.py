import asyncio
from logging import getLogger
from uuid import uuid4

from digestify_api.infrastructure.handler_registry import (
    HandlerBinding,
    HandlerRegistry,
)
from digestify_api.infrastructure.message_broker import MessageBroker

_logger = getLogger(__name__)


class MessageProcessor:
    def __init__(self, message_broker: MessageBroker) -> None:
        self._message_broker = message_broker
        self._registries: dict[str, HandlerRegistry] = {}

    def add_registry(self, registry: HandlerRegistry, service_name: str) -> None:
        if service_name in self._registries:
            raise ValueError(f"Registry for service {service_name} already exists")
        self._registries[service_name] = registry

    async def _consume_stream(self, handler_binding: HandlerBinding) -> None:
        stream_name = handler_binding.channel.get_name()
        group_name = handler_binding.handler_name
        consumer_name = uuid4().hex

        _logger.info(
            f"Starting consumer {consumer_name} for stream {stream_name} and group {group_name}"
        )
        await self._message_broker.create_consumer_group(stream_name, group_name)

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

            try:
                await handler_binding.handler(message)
                await self._message_broker.acknowledge_message(
                    stream_name, group_name, message_id
                )
                if is_autoclaim:
                    # If we successfully processed a pending message, check for more pending messages
                    iteration = 9
            except Exception:
                _logger.exception("Error while handling message")

    async def run(self) -> None:
        tasks: list[asyncio.Task[None]] = []
        for registry in self._registries.values():
            for handler_binding in registry.handlers:
                task = asyncio.create_task(self._consume_stream(handler_binding))
                tasks.append(task)
        await asyncio.gather(*tasks)
