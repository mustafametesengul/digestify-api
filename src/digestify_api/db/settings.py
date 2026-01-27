from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class DBSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_prefix="POSTGRES_",
    )

    host: str = Field(default="localhost")
    port: int = Field(default=5432)
    user: str = Field(default="user")
    password: SecretStr = Field(default=SecretStr("password"))
    db: str = Field(default="db")
