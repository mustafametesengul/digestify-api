from asyncpg import Connection


async def get_applied_migrations(conn: Connection) -> set[str]:
    rows = await conn.fetch(
        "SELECT version FROM schema_migrations",
    )
    return {r["version"] for r in rows}


async def create_schema_migrations_table(conn: Connection) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )


async def update_schema_migrations(
    conn: Connection,
    version: str,
) -> None:
    await conn.execute(
        "INSERT INTO schema_migrations (version) VALUES ($1)",
        version,
    )


async def reset_db(conn: Connection) -> None:
    await conn.execute(
        """
        DROP SCHEMA public CASCADE;
        CREATE SCHEMA public;
        GRANT ALL ON SCHEMA public TO public;
        """
    )


async def create_initial_tables(connection: Connection) -> None:
    await connection.execute(
        """
        CREATE EXTENSION IF NOT EXISTS vector;

        CREATE TABLE users (
            id UUID PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            discarded BOOLEAN NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE,
            subscription_tier TEXT NOT NULL,
            created_topics_count INTEGER NOT NULL,
            followed_topics_count INTEGER NOT NULL
        );

        CREATE INDEX ix_users_username ON users (username);
        CREATE INDEX ix_users_discarded ON users (discarded);
        CREATE INDEX ix_users_subscription_tier ON users (subscription_tier);
        CREATE INDEX ix_users_created_topics_count ON users (created_topics_count);
        CREATE INDEX ix_users_followed_topics_count ON users (followed_topics_count);

        CREATE TABLE topics (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            discarded BOOLEAN NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            language TEXT NOT NULL,
            image_url TEXT,
            embedding vector(1536) NOT NULL,
            is_active BOOLEAN NOT NULL,
            followers_count INTEGER NOT NULL
        );

        CREATE INDEX ix_topics_discarded ON topics (discarded);
        CREATE INDEX ix_topics_user_id ON topics (user_id);
        CREATE INDEX ix_topics_is_active ON topics (is_active);
        CREATE INDEX ix_topics_language ON topics (language);
        CREATE INDEX ix_topics_followers_count ON topics (followers_count);

        CREATE TABLE follows (
            user_id UUID NOT NULL,
            topic_id UUID NOT NULL,
            is_following BOOLEAN NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE,
            PRIMARY KEY (user_id, topic_id),
            CONSTRAINT fk_follows_user_id FOREIGN KEY (user_id)
                REFERENCES users (id) ON DELETE CASCADE,
            CONSTRAINT fk_follows_topic_id FOREIGN KEY (topic_id)
                REFERENCES topics (id) ON DELETE CASCADE
        );

        CREATE INDEX ix_follows_user_id ON follows (user_id);
        CREATE INDEX ix_follows_topic_id ON follows (topic_id);
        CREATE INDEX ix_follows_is_following ON follows (is_following);

        CREATE TABLE stories (
            id UUID PRIMARY KEY,
            discarded BOOLEAN NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE,
            topic_id UUID NOT NULL REFERENCES topics (id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            image_url TEXT,
            content TEXT NOT NULL,
            language TEXT NOT NULL,
            embedding vector(1536) NOT NULL
        );

        CREATE INDEX ix_stories_discarded ON stories (discarded);
        CREATE INDEX ix_stories_topic_id ON stories (topic_id);
        CREATE INDEX ix_stories_language ON stories (language);

        CREATE TABLE tasks (
            id UUID PRIMARY KEY,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE,
            name TEXT NOT NULL,
            payload JSONB NOT NULL,
            scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL,
            error_message TEXT,
            status TEXT NOT NULL
        );

        CREATE INDEX ix_tasks_status ON tasks (status);
        CREATE INDEX ix_tasks_scheduled_at ON tasks (scheduled_at);
        CREATE INDEX ix_tasks_name ON tasks (name);
        """
    )
