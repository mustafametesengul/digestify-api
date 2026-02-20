from digestify_api.identity.queries import create_tables
from digestify_api.infrastructure import message, outbox

migrations = [create_tables] + outbox.migrations + message.migrations
