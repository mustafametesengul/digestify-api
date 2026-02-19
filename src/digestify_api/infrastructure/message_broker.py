from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from redis.asyncio import Redis

import logging

from digestify_api.infrastructure.models import Message

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
        self._redis = Redis(
            host=self._settings.host,
            port=self._settings.port,
            password=self._settings.password.get_secret_value(),
            db=self._settings.db,
        )

    async def create_consumer_group(
        self,
        stream_name: str,
        group_name: str,
    ) -> None:
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

    async def publish_message(self, message: Message) -> None:
        await self._redis.xadd(
            name=message.channel,
            fields={"message": message.model_dump_json()},
        )

    async def consume_stream(
        self,
        stream_name: str,
        group_name: str,
        consumer_name: str,
    ) -> list[tuple[str, str, Message]]:
        entries = await self._redis.xreadgroup(
            group_name,
            consumer_name,
            streams={stream_name: ">"},
            count=1,
            block=1000,
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

    async def acknowledge_message(
        self,
        stream_name: str,
        group_name: str,
        message_id: str,
    ) -> None:
        await self._redis.xack(stream_name, group_name, message_id)
