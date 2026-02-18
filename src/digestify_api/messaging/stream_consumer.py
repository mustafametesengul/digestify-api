import asyncio
from logging import getLogger
from uuid import uuid4

from redis.asyncio import Redis

from digestify_api.messaging.handler_regisitry import HandlerBinding, HandlerRegistry
from digestify_api.messaging.models import Message

_logger = getLogger(__name__)


class StreamConsumer:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis
        self._registries: list[HandlerRegistry] = []
        self._tasks: list[asyncio.Task] = []

    def add_registry(self, registry: HandlerRegistry) -> None:
        self._registries.append(registry)

    async def _consume_stream(self, handler_binding: HandlerBinding) -> None:
        stream_name = handler_binding.channel
        group_name = handler_binding.handler_name
        consumer_name = uuid4().hex

        # Create consumer group if it doesn't exist
        try:
            await self._redis.xgroup_create(
                stream_name,
                group_name,
                id="0",
                mkstream=True,
            )
        except Exception:
            pass  # Group already exists

        while True:
            try:
                entries = await self._redis.xreadgroup(
                    group_name,
                    consumer_name,
                    streams={stream_name: ">"},
                    count=1,
                    block=1000,
                )
            except asyncio.CancelledError:
                break

            if not entries:
                continue

            for stream, messages in entries:
                if not isinstance(stream, str):
                    raise TypeError("Stream name must be a string")

                for message_id, fields in messages:
                    if not isinstance(fields, dict):
                        raise TypeError("Message fields must be a dictionary")

                    message_data = fields.get(b"message")
                    if not isinstance(message_data, bytes):
                        raise TypeError("Message data must be bytes")

                    message = Message.model_validate_json(message_data.decode())

                    if stream != stream_name:
                        await self._redis.xack(stream_name, group_name, message_id)
                        continue

                    try:
                        await handler_binding.handler(message)
                        await self._redis.xack(stream_name, group_name, message_id)
                    except Exception:
                        _logger.exception("Error while handling message")

    async def run(self) -> None:
        for registry in self._registries:
            for handler_binding in registry._handlers.values():
                task = asyncio.create_task(self._consume_stream(handler_binding))
                self._tasks.append(task)
        await asyncio.gather(*self._tasks)
