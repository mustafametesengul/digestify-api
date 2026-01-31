import asyncio

from digestify_api.dependencies import DBManager, DBSettings
from digestify_api.queries import (
    create_initial_tables,
    create_schema_migrations_table,
    get_applied_migrations,
    reset_db,
    update_schema_migrations,
)


async def get_applied_migrations_(db: DBManager) -> set[str]:
    async with db.get_connection() as conn:
        rows = await get_applied_migrations(conn)
        return rows


async def apply_migrations(db: DBManager) -> None:
    migrations = [
        create_initial_tables,
    ]

    async with db.get_connection() as conn:
        await create_schema_migrations_table(conn)

    applied = await get_applied_migrations_(db)

    for migration in migrations:
        version = migration.__name__

        if version in applied:
            continue

        async with db.get_connection() as conn:
            async with conn.transaction():
                await migration(connection=conn)
                await update_schema_migrations(conn, version=version)


async def reset_db_(db: DBManager) -> None:
    async with db.get_connection() as conn:
        await reset_db(conn)


async def migrations_main(settings: DBSettings | None = None) -> None:
    if settings is None:
        settings = DBSettings()

    db = DBManager(settings=settings)
    await db.init_pool()

    await apply_migrations(db)

    await db.close_pool()


if __name__ == "__main__":
    asyncio.run(migrations_main())
