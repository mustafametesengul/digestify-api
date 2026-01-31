import asyncio

from pydantic import Field
from pydantic_settings import BaseSettings, CliSubCommand, get_subcommand

from digestify_api.dependencies import DBSettings
from digestify_api.entrypoints import AppSettings, app_main, migrations_main


class Settings(BaseSettings, cli_parse_args=True):
    run: CliSubCommand[AppSettings] = Field(default=...)
    migrate: CliSubCommand[DBSettings] = Field(default=...)


def main(settings: Settings | None = None) -> None:
    settings = settings or Settings()
    subcommand = get_subcommand(settings)
    if isinstance(subcommand, AppSettings):
        app_main(subcommand)
    if isinstance(subcommand, DBSettings):
        asyncio.run(migrations_main(subcommand))


if __name__ == "__main__":
    main()
