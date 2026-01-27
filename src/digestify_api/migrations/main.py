from digestify_api.db import DBService, DBSettings
from digestify_api.migrations.service import MigrationService


async def migrations_main(settings: DBSettings | None = None) -> None:
    if settings is None:
        settings = DBSettings()

    db = DBService(settings=settings)
    await db.init_pool()

    migration_service = MigrationService(db=db)

    await migration_service.apply_migrations()

    await db.close_pool()
