from collections.abc import Awaitable, Callable, Sequence
from types import FunctionType

from asyncpg import Connection

from digestify_api.infrastructure.database import Database

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


async def get_applied_migrations_(db: Database) -> set[str]:
    async with db.transaction() as conn:
        rows = await get_applied_migrations(conn)
        return rows


async def apply_migrations(db: Database, migrations: Sequence[MigrationFunc]) -> None:
    async with db.transaction() as conn:
        if db.schema is not None:
            await create_schema(conn, db.schema)

    async with db.transaction() as conn:
        await create_schema_migrations_table(conn)

    applied = await get_applied_migrations_(db)

    for migration in migrations:
        if not isinstance(migration, FunctionType):
            raise TypeError(f"Expected a function, got {type(migration)}")

        version = migration.__name__

        if version in applied:
            continue

        async with db.transaction() as conn:
            await migration(conn)
            await update_schema_migrations(conn, version=version)
