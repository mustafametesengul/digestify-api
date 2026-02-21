from digestify_api import infrastructure

database = infrastructure.Database()
message_broker = infrastructure.MessageBroker()
outbox_publisher = infrastructure.OutboxRelay(
    database=database,
    message_broker=message_broker,
)
channel = infrastructure.Channel()


def get_database() -> infrastructure.Database:
    return database


def get_channel() -> infrastructure.Channel:
    return channel
