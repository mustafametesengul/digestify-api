from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class CouchDBSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_prefix="COUCHDB_",
    )

    url: str = Field(default="http://localhost:5984")
    user: str = Field(default="admin")
    password: SecretStr = Field(default=SecretStr("password"))


class Document(BaseModel):
    """A persistable document identified by `id` and a CouchDB revision.

    Every document carries a `type` discriminator so a single database can
    hold multiple document kinds and consumers (e.g. the `_changes` feed) can
    filter to the kind they care about. Subclasses pin it with a `Literal`
    default, for example ``type: Literal["user"] = "user"``.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(validation_alias="_id", serialization_alias="_id")
    rev: str | None = Field(
        default=None,
        validation_alias="_rev",
        serialization_alias="_rev",
    )
    type: str


class DocumentConflict(Exception):
    pass


T = TypeVar("T", bound=Document)


class DocumentRepository(ABC, Generic[T]):
    @abstractmethod
    async def get(self, id: str) -> T | None: ...

    @abstractmethod
    async def save(self, document: T) -> None: ...

    @abstractmethod
    async def find(
        self,
        selector: dict[str, Any],
        *,
        sort: list[dict[str, str]] | None = None,
        limit: int | None = None,
    ) -> list[T]:
        """Return documents matching a CouchDB Mango `selector`.

        `sort` and `limit` map directly onto the `_find` request. Sorting
        requires a matching index (see `ensure_index`).
        """
        ...


class CouchDBRepository(DocumentRepository[T]):
    def __init__(
        self,
        client: httpx.AsyncClient,
        database: str,
        document_type: type[T],
    ) -> None:
        self._client = client
        self._database = database
        self._document_type = document_type

    async def get(self, id: str) -> T | None:
        response = await self._client.get(f"/{self._database}/{id}")
        if response.status_code == httpx.codes.NOT_FOUND:
            return None
        response.raise_for_status()
        return self._document_type.model_validate(response.json())

    async def save(self, document: T) -> None:
        body = document.model_dump(by_alias=True, mode="json")
        if body.get("_rev") is None:
            body.pop("_rev", None)

        response = await self._client.put(
            f"/{self._database}/{document.id}",
            json=body,
        )
        if response.status_code == httpx.codes.CONFLICT:
            raise DocumentConflict(document.id)
        response.raise_for_status()

        document.rev = response.json()["rev"]

    async def find(
        self,
        selector: dict[str, Any],
        *,
        sort: list[dict[str, str]] | None = None,
        limit: int | None = None,
    ) -> list[T]:
        body: dict[str, Any] = {"selector": selector}
        if sort is not None:
            body["sort"] = sort
        if limit is not None:
            body["limit"] = limit

        response = await self._client.post(f"/{self._database}/_find", json=body)
        response.raise_for_status()
        return [
            self._document_type.model_validate(doc) for doc in response.json()["docs"]
        ]


async def ensure_database(client: httpx.AsyncClient, name: str) -> None:
    response = await client.put(f"/{name}")
    # 201 Created on first run, 412 Precondition Failed if it already exists.
    if response.status_code in (httpx.codes.CREATED, httpx.codes.PRECONDITION_FAILED):
        return
    response.raise_for_status()


async def ensure_index(
    client: httpx.AsyncClient,
    database: str,
    *,
    fields: list[str],
    name: str,
) -> None:
    """Create a Mango index if it does not already exist.

    `_index` is idempotent: CouchDB returns 200 whether it created the index
    or found an existing one with the same definition.
    """
    response = await client.post(
        f"/{database}/_index",
        json={"index": {"fields": fields}, "name": name, "type": "json"},
    )
    response.raise_for_status()
