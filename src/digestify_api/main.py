import asyncio

from pydantic import Field
from pydantic_settings import BaseSettings, CliSubCommand, get_subcommand

from digestify_api.dependencies import db_manager
from digestify_api.entrypoints import app, migrations


class Settings(BaseSettings, cli_parse_args=True):
    run: CliSubCommand[app.AppSettings] = Field(default=...)
    migrate: CliSubCommand[db_manager.DBSettings] = Field(default=...)


def main(settings: Settings | None = None) -> None:
    settings = settings or Settings()
    subcommand = get_subcommand(settings)
    if isinstance(subcommand, app.AppSettings):
        app.app_main(subcommand)
    if isinstance(subcommand, db_manager.DBSettings):
        asyncio.run(migrations.migrations_main(subcommand))


if __name__ == "__main__":
    main()
