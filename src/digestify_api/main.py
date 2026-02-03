import asyncio

from pydantic import Field
from pydantic_settings import BaseSettings, CliSubCommand, get_subcommand

from digestify_api import dependencies, entrypoints


class Settings(BaseSettings, cli_parse_args=True):
    run: CliSubCommand[entrypoints.app.AppSettings] = Field(default=...)
    migrate: CliSubCommand[dependencies.db.DBSettings] = Field(default=...)


def main(settings: Settings | None = None) -> None:
    settings = settings or Settings()
    subcommand = get_subcommand(settings)
    if isinstance(subcommand, entrypoints.app.AppSettings):
        entrypoints.app.app_main(subcommand)
    if isinstance(subcommand, dependencies.db.DBSettings):
        asyncio.run(entrypoints.migrations.migrations_main(subcommand))


if __name__ == "__main__":
    main()
