from collections.abc import AsyncIterator, Collection
from contextlib import asynccontextmanager
from typing import Self

import httpx
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from digestify_api.couchdb.database import Database


class ClientSettings(BaseSettings):
    """Connection settings, read from `COUCHDB_*` environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_prefix="COUCHDB_",
    )

    url: str = "http://localhost:5984"
    user: str = "admin"
    password: SecretStr = SecretStr("password")
    database_prefix: str = "digestify"


class Client:
    """A connection to a CouchDB server; hands out `Database` handles."""

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        *,
        database_prefix: str = "",
    ) -> None:
        self._http_client = http_client
        self._database_prefix = database_prefix

    def get_database(self, name: str) -> Database:
        if self._database_prefix:
            name = f"{self._database_prefix}-{name}"
        return Database(self._http_client, name)

    async def ensure_databases(self, names: Collection[str]) -> None:
        for name in names:
            await self.get_database(name).ensure_database()

    @classmethod
    @asynccontextmanager
    async def connect(
        cls,
        settings: ClientSettings | None = None,
    ) -> AsyncIterator[Self]:
        settings = settings or ClientSettings()
        async with httpx.AsyncClient(
            base_url=settings.url,
            auth=(settings.user, settings.password.get_secret_value()),
            timeout=httpx.Timeout(10.0),
        ) as client:
            yield cls(client, database_prefix=settings.database_prefix)
