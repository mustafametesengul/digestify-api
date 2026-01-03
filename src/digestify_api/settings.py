from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    debug: bool = Field(default=...)
    jwks_url: str = Field(default=...)
    postgres_host: str = Field(default=...)
    postgres_port: int = Field(default=...)
    postgres_user: str = Field(default=...)
    postgres_password: str = Field(default=...)
    postgres_db: str = Field(default=...)
    openai_api_key: str = Field(default=...)


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        raise ValueError("Settings have not been initialized.")
    return _settings


def init_settings() -> None:
    global _settings
    _settings = Settings()
