import asyncio

from digestify_api.dependencies import db_manager
from digestify_api.queries import migration_queries


async def get_applied_migrations_(db: db_manager.DBManager) -> set[str]:
    async with db.get_connection() as conn:
        rows = await migration_queries.get_applied_migrations(conn)
        return rows


async def apply_migrations(db: db_manager.DBManager) -> None:
    migrations = [
        migration_queries.create_initial_tables,
    ]

    async with db.get_connection() as conn:
        await migration_queries.create_schema_migrations_table(conn)

    applied = await get_applied_migrations_(db)

    for migration in migrations:
        version = migration.__name__

        if version in applied:
            continue

        async with db.get_connection() as conn:
            async with conn.transaction():
                await migration(connection=conn)
                await migration_queries.update_schema_migrations(conn, version=version)


async def reset_db_(db: db_manager.DBManager) -> None:
    async with db.get_connection() as conn:
        await migration_queries.reset_db(conn)


async def migrations_main(settings: db_manager.DBSettings | None = None) -> None:
    if settings is None:
        settings = db_manager.DBSettings()

    db = db_manager.DBManager(settings=settings)
    await db.init_pool()

    await apply_migrations(db)

    await db.close_pool()


if __name__ == "__main__":
    asyncio.run(migrations_main())
