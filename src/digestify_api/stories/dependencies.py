from digestify_api import infrastructure

database = infrastructure.database.Database()
message_broker = infrastructure.message_broker.MessageBroker()
channel = infrastructure.channel.Channel()


def get_database() -> infrastructure.database.Database:
    return database
