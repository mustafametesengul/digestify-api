from fastapi import APIRouter

from digestify_api.infrastructure import (
    Channel,
    Database,
    HandlerRegistry,
    MessageBroker,
)

message_broker = MessageBroker()

channel = Channel()

router = APIRouter()

database = Database()

handler_registry = HandlerRegistry(
    channel=channel,
    database=database,
)


def get_database() -> Database:
    return database
