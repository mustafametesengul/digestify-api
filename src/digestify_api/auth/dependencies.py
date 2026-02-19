from redis.asyncio import Redis

from digestify_api.db import Database, DatabaseSettings
from digestify_api.messaging import OutboxRelay, RedisSettings

database = Database(settings=DatabaseSettings(db_schema="auth"))
redis_settings = RedisSettings()
redis = Redis(
    host=redis_settings.host,
    port=redis_settings.port,
    password=redis_settings.password.get_secret_value(),
    db=redis_settings.db,
)
outbox_publisher = OutboxRelay(database=database, redis=redis)


def get_database() -> Database:
    return database
