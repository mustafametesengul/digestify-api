from asyncpg import Connection

from digestify_api import infrastructure


async def create_initial_tables(connection: Connection) -> None:
    await connection.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY,
            created_topics_count INTEGER NOT NULL,
            active_topics_count INTEGER NOT NULL,
            is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ
        );

        CREATE TABLE IF NOT EXISTS topics (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            language TEXT NOT NULL,
            image_url TEXT,
            is_active BOOLEAN NOT NULL,
            is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ,
            schedule_time TIME NOT NULL,
            schedule_timezone TEXT NOT NULL,
            schedule_version INT NOT NULL,
            last_execution_date DATE
        );

        CREATE TABLE IF NOT EXISTS stories (
            id UUID PRIMARY KEY,
            topic_id UUID NOT NULL,
            title TEXT NOT NULL,
            image_url TEXT,
            content TEXT NOT NULL,
            language TEXT NOT NULL,
            is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ
        );
        """
    )


migrations = infrastructure.migrations + [create_initial_tables]
