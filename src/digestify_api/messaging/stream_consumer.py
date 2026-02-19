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

    def add_registry(self, registry: HandlerRegistry) -> None:
        self._registries.append(registry)

    async def _consume_stream(self, handler_binding: HandlerBinding) -> None:
        stream_name = handler_binding.channel
        group_name = handler_binding.handler_name
        consumer_name = uuid4().hex

        _logger.info(
            f"Starting consumer {consumer_name} for stream {stream_name} and group {group_name}"
        )

        try:
            await self._redis.xgroup_create(
                stream_name,
                group_name,
                id="0",
                mkstream=True,
            )
        except Exception:
            _logger.warning(
                f"Consumer group {group_name} already exists for stream {stream_name}"
            )
            pass

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
                if not isinstance(stream, bytes):
                    msg = "Stream name must be bytes"
                    _logger.exception(msg)
                    raise TypeError(msg)

                for message_id, fields in messages:
                    if not isinstance(fields, dict):
                        msg = "Message fields must be a dictionary"
                        _logger.exception(msg)
                        raise TypeError(msg)

                    message_data = fields.get(b"message")
                    if not isinstance(message_data, bytes):
                        msg = "Message data must be bytes"
                        _logger.exception(msg)
                        raise TypeError(msg)

                    message = Message.model_validate_json(message_data.decode())

                    stream_decoded = stream.decode()

                    if stream_decoded != stream_name:
                        await self._redis.xack(stream_name, group_name, message_id)
                        continue

                    try:
                        await handler_binding.handler(message)
                        await self._redis.xack(stream_name, group_name, message_id)
                    except Exception:
                        _logger.exception("Error while handling message")

    async def run(self) -> None:
        tasks: list[asyncio.Task[None]] = []
        for registry in self._registries:
            for handler_binding in registry.handlers:
                task = asyncio.create_task(self._consume_stream(handler_binding))
                tasks.append(task)
        await asyncio.gather(*tasks)
