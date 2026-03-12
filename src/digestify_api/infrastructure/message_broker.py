import logging

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from redis.asyncio import Redis

from digestify_api.infrastructure.message import Message

_logger = logging.getLogger(__name__)


class MessageBrokerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_prefix="REDIS_",
    )

    host: str = Field(default="localhost")
    port: int = Field(default=6379)
    password: SecretStr = Field(default=SecretStr("password"))
    db: str = Field(default="0")


class MessageBroker:
    def __init__(self, settings: MessageBrokerSettings | None = None) -> None:
        self._settings = settings or MessageBrokerSettings()
        self._redis: Redis | None = None

    @property
    def redis(self) -> Redis:
        if self._redis is None:
            raise RuntimeError("Message broker is not initialized")
        return self._redis

    async def connect(self) -> None:
        self._redis = Redis(
            host=self._settings.host,
            port=self._settings.port,
            password=self._settings.password.get_secret_value(),
            db=self._settings.db,
        )

    async def close(self) -> None:
        await self.redis.close()

    async def create_consumer_group(
        self,
        stream_name: str,
        group_name: str,
    ) -> None:
        try:
            await self.redis.xgroup_create(
                stream_name,
                group_name,
                id="0",
                mkstream=True,
            )
        except Exception:
            _logger.warning(
                f"Consumer group {group_name} already exists for stream {stream_name}"
            )

    async def publish_message(self, message: Message) -> None:
        await self.redis.xadd(
            name=message.channel,
            fields={"message": message.model_dump_json()},
        )

    async def consume_stream(
        self,
        stream_name: str,
        group_name: str,
        consumer_name: str,
        count: int = 1,
        block: int = 1000,
        start_id: str = ">",
    ) -> list[tuple[str, str, Message]]:
        entries = await self.redis.xreadgroup(
            group_name,
            consumer_name,
            streams={stream_name: start_id},
            count=count,
            block=block,
        )

        broker_messages: list[tuple[str, str, Message]] = []

        if not entries:
            return broker_messages

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

                if not isinstance(message_id, bytes):
                    msg = "Message ID must be bytes"
                    _logger.exception(msg)
                    raise TypeError(msg)

                message = Message.model_validate_json(message_data.decode())

                broker_messages.append((stream.decode(), message_id.decode(), message))

        return broker_messages

    async def autoclaim_messages(
        self,
        stream_name: str,
        group_name: str,
        consumer_name: str,
        min_idle_time: int = 60000,
        start_id: str = "0-0",
        count: int = 1,
    ) -> tuple[str, list[tuple[str, str, Message]]]:
        result = await self.redis.xautoclaim(
            name=stream_name,
            groupname=group_name,
            consumername=consumer_name,
            min_idle_time=min_idle_time,
            start_id=start_id,
            count=count,
        )

        next_start_id = result[0]
        messages = result[1]

        broker_messages: list[tuple[str, str, Message]] = []

        if not messages:
            return next_start_id.decode() if isinstance(
                next_start_id, bytes
            ) else next_start_id, broker_messages

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

            if not isinstance(message_id, bytes):
                msg = "Message ID must be bytes"
                _logger.exception(msg)
                raise TypeError(msg)

            message = Message.model_validate_json(message_data.decode())
            broker_messages.append((stream_name, message_id.decode(), message))

        return next_start_id.decode() if isinstance(
            next_start_id, bytes
        ) else next_start_id, broker_messages

    async def acknowledge_message(
        self,
        stream_name: str,
        group_name: str,
        message_id: str,
    ) -> None:
        await self.redis.xack(stream_name, group_name, message_id)

    async def delete_ghost_consumers(
        self,
        stream_name: str,
        group_name: str,
        min_idle_time: int = 60000,
    ) -> None:
        try:
            consumers = await self.redis.xinfo_consumers(stream_name, group_name)
            for consumer in consumers:
                idle = consumer.get("idle", 0)
                pending = consumer.get("pending", 0)
                name = consumer.get("name")

                if pending == 0 and idle > min_idle_time:
                    await self.redis.xgroup_delconsumer(stream_name, group_name, name)
        except Exception as e:
            _logger.warning(
                f"Failed to delete ghost consumers for stream {stream_name} and group {group_name}: {e}"
            )
