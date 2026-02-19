from redis.asyncio import Redis

from digestify_api.infrastructure import Da, StreamConsumer
from digestify_api.stories.handlers import handler_registry

database = Database()

stream_consumer = StreamConsumer(redis=redis)
stream_consumer.add_registry(handler_registry)


def get_database() -> Database:
    return database
