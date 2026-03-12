from fastapi import APIRouter

from digestify_api import infrastructure
from digestify_api.infrastructure import (
    Channel,
    Database,
    MessageBroker,
    OperationRegistry,
)
from digestify_api.topics import story, topic, user

message_broker = MessageBroker()

events = Channel()
commands = Channel()

router = APIRouter()

database = Database()

operation_registry = OperationRegistry()


def get_database() -> Database:
    return database


migrations = infrastructure.migrations + [
    topic.create_tables,
    user.create_tables,
    story.create_tables,
]
