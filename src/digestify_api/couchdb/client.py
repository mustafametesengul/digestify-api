from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Self

import httpx
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from digestify_api.couchdb.database import Database


class CouchDBSettings(BaseSettings):
    """Connection settings, read from `COUCHDB_*` environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_prefix="COUCHDB_",
    )

    url: str = "http://localhost:5984"
    user: str = "admin"
    password: SecretStr = SecretStr("password")


class CouchDB:
    """A connection to a CouchDB server; hands out `Database` handles."""

    def __init__(
        self,
        client: httpx.AsyncClient,
    ) -> None:
        self._client = client

    def get_database(self, name: str) -> Database:
        return Database(self._client, name)

    @classmethod
    @asynccontextmanager
    async def connect(
        cls,
        settings: CouchDBSettings | None = None,
    ) -> AsyncIterator[Self]:
        settings = settings or CouchDBSettings()
        async with httpx.AsyncClient(
            base_url=settings.url,
            auth=(settings.user, settings.password.get_secret_value()),
            # `read` stays unbounded so a continuous `_changes` feed can idle
            # between heartbeats without timing out.
            timeout=httpx.Timeout(connect=10.0, read=None, write=10.0, pool=10.0),
        ) as client:
            yield cls(client)
