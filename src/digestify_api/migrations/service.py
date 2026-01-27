from digestify_api.db import DBService
from digestify_api.migrations.migrations import create_initial_tables
from digestify_api.migrations.repository import MigrationRepository


class MigrationService:
    def __init__(
        self,
        db: DBService,
    ) -> None:
        self._db = db

    async def get_applied_migrations(self) -> set[str]:
        async with self._db.get_connection() as conn:
            repository = MigrationRepository(conn)
            rows = await repository.get_applied_migrations()
            return rows

    async def apply_migrations(self) -> None:
        migrations = [
            create_initial_tables,
        ]

        async with self._db.get_connection() as conn:
            repository = MigrationRepository(conn)
            await repository.create_schema_migrations_table()

        applied = await self.get_applied_migrations()

        for migration in migrations:
            version = migration.__name__

            if version in applied:
                continue

            async with self._db.get_connection() as conn:
                repository = MigrationRepository(conn)
                async with conn.transaction():
                    await migration(connection=conn)
                    await repository.update_schema_migrations(version=version)

    async def reset_db(self) -> None:
        async with self._db.get_connection() as conn:
            repository = MigrationRepository(conn)
            await repository.reset_db()
