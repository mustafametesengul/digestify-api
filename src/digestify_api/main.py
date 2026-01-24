import asyncio

from pydantic import Field
from pydantic_settings import BaseSettings, CliSubCommand, get_subcommand

from digestify_api.app import AppSettings, run_app
from digestify_api.db import DBSettings
from digestify_api.migrations import apply_migrations_main


class Settings(BaseSettings, cli_parse_args=True):
    run: CliSubCommand[AppSettings] = Field(default=...)
    migrate: CliSubCommand[DBSettings] = Field(default=...)


def main(settings: Settings | None = None) -> None:
    settings = settings or Settings()
    subcommand = get_subcommand(settings)
    if isinstance(subcommand, AppSettings):
        run_app(subcommand)
    if isinstance(subcommand, DBSettings):
        asyncio.run(apply_migrations_main(subcommand))


if __name__ == "__main__":
    main()
