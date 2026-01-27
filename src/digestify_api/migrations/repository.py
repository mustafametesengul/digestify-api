from asyncpg import Connection


class MigrationRepository:
    def __init__(
        self,
        connection: Connection,
    ) -> None:
        self._connection = connection

    async def get_applied_migrations(self) -> set[str]:
        rows = await self._connection.fetch(
            "SELECT version FROM schema_migrations",
        )
        return {r["version"] for r in rows}

    async def create_schema_migrations_table(self) -> None:
        await self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            """
        )

    async def update_schema_migrations(
        self,
        version: str,
    ) -> None:
        await self._connection.execute(
            "INSERT INTO schema_migrations (version) VALUES ($1)",
            version,
        )

    async def reset_db(self) -> None:
        await self._connection.execute(
            """
            DROP SCHEMA public CASCADE;
            CREATE SCHEMA public;
            GRANT ALL ON SCHEMA public TO public;
            """
        )
