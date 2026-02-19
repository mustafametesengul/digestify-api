from redis.asyncio import Redis

from digestify_api.db import Database, DatabaseSettings
from digestify_api.messaging import StreamConsumer
from digestify_api.stories.handlers import handler_registry

database = Database(settings=DatabaseSettings(schema="stories"))
redis = Redis(password="password")
stream_consumer = StreamConsumer(redis=redis)
stream_consumer.add_registry(handler_registry)


def get_database() -> Database:
    return database
