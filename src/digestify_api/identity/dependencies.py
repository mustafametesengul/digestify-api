from digestify_api.infrastructure import Channel, Database, MessageBroker, OutboxRelay

database = Database()
message_broker = MessageBroker()
outbox_publisher = OutboxRelay(database=database, message_broker=message_broker)
channel = Channel()


def get_database() -> Database:
    return database
