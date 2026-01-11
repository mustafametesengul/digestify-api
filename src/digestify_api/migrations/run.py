from pathlib import Path

from alembic import command
from alembic.config import Config

from digestify_api.db import DBSettings, create_database_url


def run_migrations(settings: DBSettings | None = None) -> None:
    settings = settings or DBSettings()
    db_url = create_database_url(
        driver="postgresql+asyncpg",
        user=settings.user,
        password=settings.password,
        host=settings.host,
        port=settings.port,
        db=settings.db,
    )
    script_location = Path(__file__).parent.as_posix()

    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", script_location)
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "head")
