from digestify_api.infrastructure.channel import Channel
from digestify_api.infrastructure.database import Database
from digestify_api.infrastructure.message_broker import MessageBroker
from digestify_api.infrastructure.outbox import OutboxRelay

database = Database()
message_broker = MessageBroker()
outbox_publisher = OutboxRelay(database=database, message_broker=message_broker)
channel = Channel()


def get_database() -> Database:
    return database
