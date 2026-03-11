from fastapi import APIRouter

from digestify_api import infrastructure
from digestify_api.identity.user import create_tables
from digestify_api.infrastructure import Channel, Database, MessageBroker, OutboxRelay

router = APIRouter()

database = Database()

message_broker = MessageBroker()
outbox_relay = OutboxRelay(
    database=database,
    message_broker=message_broker,
)
events = Channel()


migrations = infrastructure.migrations + [create_tables]


def get_database() -> Database:
    return database


def get_events_channel() -> Channel:
    return events
