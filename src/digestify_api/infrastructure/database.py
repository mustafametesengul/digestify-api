import json
import operator
from contextlib import asynccontextmanager
from functools import reduce
from typing import Annotated, Any, AsyncIterator, Generic, TypeVar

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr, TypeAdapter
from pydantic_settings import BaseSettings, SettingsConfigDict


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


class Change(BaseModel, Generic[T]):
    """A single row from the `_changes` feed.

    `seq` is the feed position to resume from; persist it after the change is
    durably handled so a restart replays no more than the last unfinished
    change. `doc` is populated only for live documents that match the feed's
    type filter — it is ``None`` for deletions (where only `id` is meaningful).
    """

    seq: str
    id: str
    deleted: bool = False
    doc: T | None = None


class Database(Generic[T]):
    def __init__(
        self,
        client: httpx.AsyncClient,
        name: str,
        *document_types: type[T],
    ) -> None:
        self._client = client
        self._name = name
        union: Any = reduce(operator.or_, document_types)
        annotation: Any = Annotated[union, Field(discriminator="type")]
        self._adapter = TypeAdapter(annotation)

    async def ensure_index(
        self,
        *,
        name,
        fields: list[str],
    ) -> None:
        """Create a Mango index if it does not already exist.

        `_index` is idempotent: CouchDB returns 200 whether it created the index
        or found an existing one with the same definition.
        """
        response = await self._client.post(
            url=f"/{self._name}/_index",
            json={"index": {"fields": fields}, "name": name, "type": "json"},
        )
        response.raise_for_status()

    async def get(self, id: str) -> T | None:
        response = await self._client.get(f"/{self._name}/{id}")
        if response.status_code == httpx.codes.NOT_FOUND:
            return None
        response.raise_for_status()
        return self._adapter.validate_python(response.json())

    async def save(self, document: T) -> None:
        body: dict[str, Any] = document.model_dump(by_alias=True, mode="json")
        if body.get("_rev") is None:
            body.pop("_rev", None)

        response = await self._client.put(
            f"/{self._name}/{document.id}",
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

        response = await self._client.post(f"/{self._name}/_find", json=body)
        response.raise_for_status()
        return [self._adapter.validate_python(doc) for doc in response.json()["docs"]]

    async def changes(
        self,
        *,
        since: str = "0",
        selector: dict[str, Any] | None = None,
        include_docs: bool = True,
        heartbeat: int = 30_000,
    ) -> AsyncIterator[Change[T]]:
        """Tail the continuous `_changes` feed, yielding one `Change` per row.

        The feed runs forever; iterate to consume and break to stop. Heartbeat
        keep-alives and the feed's closing `last_seq` row are filtered out, so
        every yielded `Change` carries a real `id` and `seq`. Pass `selector`
        to filter server-side (e.g. ``{"type": "user"}``) and `since` to resume
        from a previously persisted `Change.seq`.
        """
        params: dict[str, Any] = {
            "feed": "continuous",
            "since": since,
            "include_docs": "true" if include_docs else "false",
            "heartbeat": str(heartbeat),
        }
        body: dict[str, Any] = {}
        if selector is not None:
            params["filter"] = "_selector"
            body["selector"] = selector

        async with self._client.stream(
            "POST",
            f"/{self._name}/_changes",
            params=params,
            json=body,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.strip():
                    continue  # heartbeat keep-alive
                row: dict[str, Any] = json.loads(line)
                # The final row of a closing feed is {"last_seq": ...}, no "id".
                if "id" not in row or "seq" not in row:
                    continue

                deleted = bool(row.get("deleted"))
                raw_doc = row.get("doc")
                # Tombstones carry no `type`, so they cannot pass the
                # discriminated-union adapter; surface them by id only.
                doc = (
                    self._adapter.validate_python(raw_doc)
                    if raw_doc is not None and not deleted
                    else None
                )
                yield Change(seq=row["seq"], id=row["id"], deleted=deleted, doc=doc)


class ClientSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_prefix="COUCHDB_",
    )

    url: str = Field(default="http://localhost:5984")
    user: str = Field(default="admin")
    password: SecretStr = Field(default=SecretStr("password"))


class Client:
    def __init__(
        self,
        client: httpx.AsyncClient,
    ) -> None:
        self._client = client

    async def ensure_database(self, name: str) -> None:
        response = await self._client.put(f"/{name}")
        # 201 Created on first run, 412 Precondition Failed if it already exists.
        if response.status_code in (
            httpx.codes.CREATED,
            httpx.codes.PRECONDITION_FAILED,
        ):
            return
        response.raise_for_status()

    def get_database(self, name: str, *document_types: type[T]) -> Database[T]:
        return Database(self._client, name, *document_types)


@asynccontextmanager
async def create_client(
    settings: ClientSettings | None = None,
) -> AsyncIterator[Client]:
    settings = settings or ClientSettings()
    async with httpx.AsyncClient(
        base_url=settings.url,
        auth=(settings.user, settings.password.get_secret_value()),
        timeout=httpx.Timeout(connect=10.0, read=None, write=10.0, pool=10.0),
    ) as client:
        yield Client(client)
