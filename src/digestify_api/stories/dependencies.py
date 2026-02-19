from redis.asyncio import Redis

from digestify_api.db import Database, DatabaseSettings
from digestify_api.messaging import RedisSettings, StreamConsumer
from digestify_api.stories.handlers import handler_registry

database = Database(settings=DatabaseSettings(db_schema="stories"))
redis_settings = RedisSettings()
redis = Redis(
    host=redis_settings.host,
    port=redis_settings.port,
    password=redis_settings.password.get_secret_value(),
    db=redis_settings.db,
)
stream_consumer = StreamConsumer(redis=redis)
stream_consumer.add_registry(handler_registry)


def get_database() -> Database:
    return database
