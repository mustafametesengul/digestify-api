from digestify_api.infrastructure.channel import Channel
from digestify_api.infrastructure.database import Database
from digestify_api.infrastructure.message_broker import MessageBroker

database = Database()
message_broker = MessageBroker()
channel = Channel()


def get_database() -> Database:
    return database
