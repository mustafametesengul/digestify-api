from digestify_api.messaging.queries import (
    add_channel_column,
    create_messaging_tables,
)

migrations = [create_messaging_tables, add_channel_column]
