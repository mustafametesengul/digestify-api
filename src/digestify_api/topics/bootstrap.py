from fastapi import APIRouter

from digestify_api.infrastructure import (
    Channel,
    Database,
    MessageBroker,
    OperationRegistry,
)

message_broker = MessageBroker()

events = Channel()
commands = Channel()

router = APIRouter()

database = Database()

operation_registry = OperationRegistry()


def get_database() -> Database:
    return database
