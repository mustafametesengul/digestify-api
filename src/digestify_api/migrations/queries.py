from asyncpg import Connection


async def create_schema(conn: Connection, schema: str) -> None:
    await conn.execute(
        f"""
        CREATE SCHEMA IF NOT EXISTS {schema};
        """
    )


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
