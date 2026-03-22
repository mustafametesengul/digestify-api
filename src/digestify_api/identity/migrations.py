from asyncpg import Connection

from digestify_api import infrastructure


async def create_initial_tables(connection: Connection) -> None:
    await connection.execute(
        """
        CREATE TABLE users (
            id UUID PRIMARY KEY,
            username TEXT UNIQUE,
            password_hash TEXT,
            is_deleted BOOLEAN NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE,
            version INTEGER NOT NULL
        );

        CREATE INDEX ix_users_is_deleted ON users (is_deleted);
        """
    )


migrations = infrastructure.migrations + [create_initial_tables]
