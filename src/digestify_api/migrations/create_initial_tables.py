from asyncpg import Connection


async def create_initial_tables(connection: Connection) -> None:
    await connection.execute(
        """
        CREATE TABLE users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            discarded BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            followed_topics_count INTEGER NOT NULL DEFAULT 0
        );

        CREATE INDEX ix_users_discarded ON users (discarded);
        CREATE INDEX ix_users_followed_topics_count ON users (followed_topics_count);

        CREATE TABLE topics (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            discarded BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            followers_count INTEGER NOT NULL DEFAULT 0  
        );

        CREATE INDEX ix_topics_discarded ON topics (discarded);
        CREATE INDEX ix_topics_followers_count ON topics (followers_count);

        CREATE TABLE follows (
            user_id UUID NOT NULL,
            topic_id UUID NOT NULL,
            is_following BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
        );
        """
    )
