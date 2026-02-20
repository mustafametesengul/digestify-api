from digestify_api.infrastructure import Channel, Database, MessageBroker

database = Database()
message_broker = MessageBroker()
channel = Channel()


def get_database() -> Database:
    return database
