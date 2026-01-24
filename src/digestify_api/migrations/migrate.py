import asyncio

import asyncpg

from digestify_api.db import DBSettings
from digestify_api.migrations.create_initial_tables import (
    create_initial_tables,
)


async def get_applied_migrations(conn: asyncpg.Connection) -> set[str]:
    rows = await conn.fetch("SELECT version FROM schema_migrations")
    return {r["version"] for r in rows}


async def apply_migrations(conn: asyncpg.Connection) -> None:
    migrations = [create_initial_tables]

    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )

    applied = await get_applied_migrations(conn)

    for migration in migrations:
        version = migration.__name__

        if version in applied:
            continue

        print(f"Applying {version}")

        async with conn.transaction():
            await migration(connection=conn)
            await conn.execute(
                "INSERT INTO schema_migrations (version) VALUES ($1)",
                version,
            )

    print("Migrations complete")


async def apply_migrations_main(settings: DBSettings | None = None) -> None:
    if settings is None:
        settings = DBSettings()
    dsn = (
        f"postgresql://{settings.user}:{settings.password}"
        f"@{settings.host}:{settings.port}/{settings.db}"
    )
    conn = await asyncpg.connect(dsn)
    if not isinstance(conn, asyncpg.Connection):
        raise RuntimeError("Failed to establish database connection")
    try:
        await apply_migrations(conn)

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(apply_migrations_main())
