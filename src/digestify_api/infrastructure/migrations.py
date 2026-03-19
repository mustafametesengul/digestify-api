from asyncpg import Connection


async def create_infrastructure_tables(connection: Connection) -> None:
    await connection.execute(
        """
        CREATE TABLE messages (
            id UUID PRIMARY KEY,
            channel TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL,
            type TEXT NOT NULL,
            payload JSONB NOT NULL,
            scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL
        );

        CREATE INDEX ix_messages_scheduled_at ON messages (scheduled_at);
        CREATE INDEX ix_messages_type ON messages (type);

        CREATE TABLE outbox (
            id UUID PRIMARY KEY,
            channel TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL,
            type TEXT NOT NULL,
            payload JSONB NOT NULL,
            scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL
        );

        CREATE INDEX ix_outbox_scheduled_at ON outbox (scheduled_at);
        CREATE INDEX ix_outbox_type ON outbox (type);

        CREATE TABLE handled_messages (
            message_id UUID NOT NULL,
            handler_name TEXT NOT NULL,
            handled_at TIMESTAMP WITH TIME ZONE NOT NULL,
            PRIMARY KEY (message_id, handler_name)
        );

        CREATE INDEX ix_handled_messages_handled_at ON handled_messages (handled_at);
        """
    )


migrations = [create_infrastructure_tables]
