import asyncio

from digestify_api import messaging
from digestify_api.auth.dependencies import database
from digestify_api.auth.queries import create_tables
from digestify_api.migrations import apply_migrations

migrations = [create_tables] + messaging.migrations


async def main() -> None:
    print("Applying migrations...")
    await database.init_pool()
    await apply_migrations(database, migrations)
    await database.close_pool()
    print("Migrations applied successfully.")


if __name__ == "__main__":
    asyncio.run(main())
