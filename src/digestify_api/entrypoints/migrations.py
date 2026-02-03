import asyncio

from digestify_api import dependencies, queries


async def get_applied_migrations_(db: dependencies.db.DBManager) -> set[str]:
    async with db.get_connection() as conn:
        rows = await queries.migrations.get_applied_migrations(conn)
        return rows


async def apply_migrations(db: dependencies.db.DBManager) -> None:
    migrations = [
        queries.migrations.create_initial_tables,
    ]

    async with db.get_connection() as conn:
        await queries.migrations.create_schema_migrations_table(conn)

    applied = await get_applied_migrations_(db)

    for migration in migrations:
        version = migration.__name__

        if version in applied:
            continue

        async with db.get_connection() as conn:
            async with conn.transaction():
                await migration(connection=conn)
                await queries.migrations.update_schema_migrations(conn, version=version)


async def reset_db_(db: dependencies.db.DBManager) -> None:
    async with db.get_connection() as conn:
        await queries.migrations.reset_db(conn)


async def migrations_main(settings: dependencies.db.DBSettings | None = None) -> None:
    if settings is None:
        settings = dependencies.db.DBSettings()

    db = dependencies.db.DBManager(settings=settings)
    await db.init_pool()

    await apply_migrations(db)

    await db.close_pool()


if __name__ == "__main__":
    asyncio.run(migrations_main())
