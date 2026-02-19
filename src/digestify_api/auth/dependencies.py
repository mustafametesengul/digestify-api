from redis.asyncio import Redis

from digestify_api.db import Database, DatabaseSettings
from digestify_api.messaging import OutboxRelay

database = Database(settings=DatabaseSettings(schema="auth"))

redis = Redis(password="password")
outbox_publisher = OutboxRelay(database=database, redis=redis)


def get_database() -> Database:
    return database
