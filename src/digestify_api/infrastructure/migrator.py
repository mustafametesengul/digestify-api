from collections.abc import Awaitable, Callable, Sequence
from types import FunctionType

import asyncpg
from asyncpg import Connection

from digestify_api.infrastructure.database import DSNSettings, get_dsn

MigrationFunc = Callable[[Connection], Awaitable[None]]


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


async def apply_migrations(
    schema: str,
    migrations: Sequence[MigrationFunc],
    dsn_settings: DSNSettings | None = None,
) -> None:
    dsn_settings = dsn_settings or DSNSettings()
    dsn = get_dsn(dsn_settings)
    connection = await asyncpg.connect(dsn)

    if not isinstance(connection, Connection):
        raise TypeError("Expected asyncpg.Connection")

    await create_schema(connection, schema)

    await connection.execute(f"SET search_path TO {schema}")

    await create_schema_migrations_table(connection)

    applied = await get_applied_migrations(connection)

    for migration in migrations:
        if not isinstance(migration, FunctionType):
            raise TypeError(f"Expected a function, got {type(migration)}")

        version = f"{migration.__name__}"
        if version in applied:
            continue

        async with connection.transaction():
            await migration(connection)
            await update_schema_migrations(connection, version=version)

    await connection.close()
