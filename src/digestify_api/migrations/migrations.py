from digestify_api.infrastructure import Database
from digestify_api.migrations.queries import (
    create_schema,
    create_schema_migrations_table,
    get_applied_migrations,
    update_schema_migrations,
)


async def get_applied_migrations_(db: Database) -> set[str]:
    async with db.transaction() as conn:
        rows = await get_applied_migrations(conn)
        return rows


async def apply_migrations(db: Database, migrations: list, schema: str) -> None:
    async with db.transaction() as conn:
        await create_schema(conn, schema)

    async with db.transaction() as conn:
        await create_schema_migrations_table(conn)

    applied = await get_applied_migrations_(db)

    for migration in migrations:
        version = migration.__name__

        if version in applied:
            continue

        async with db.transaction() as conn:
            await migration(connection=conn)
            await update_schema_migrations(conn, version=version)
