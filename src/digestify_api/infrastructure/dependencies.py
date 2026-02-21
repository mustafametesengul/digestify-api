from digestify_api.infrastructure.handled_message import create_handled_messages_table
from digestify_api.infrastructure.message import create_messages_table
from digestify_api.infrastructure.outbox import create_outbox_table

migrations = [
    create_outbox_table,
    create_messages_table,
    create_handled_messages_table,
]
