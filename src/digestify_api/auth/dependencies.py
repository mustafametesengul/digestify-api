from digestify_api.db import Database, DatabaseSettings
from digestify_api.messaging import OutboxRelay

database = Database(settings=DatabaseSettings(schema="auth"))
outbox_publisher = OutboxRelay(database=database)


def get_database() -> Database:
    return database
