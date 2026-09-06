import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

import httpx


class DocumentConflict(Exception):
    """Raised when a write loses against a newer revision of the document."""


@dataclass(slots=True, frozen=True)
class Change:
    """A single row from the `_changes` feed.

    `seq` is the feed position to resume from; persist it after the change is
    durably handled so a restart replays no more than the last unfinished
    change. `doc` is the live document body; it is ``None`` for deletions
    (tombstones carry nothing useful beyond `id`) and when the feed was
    requested without document bodies.
    """

    seq: str
    id: str
    deleted: bool
    doc: dict[str, Any] | None


class Database:
    """A single CouchDB database, exposing document-level operations.

    Documents are plain dicts at this layer; `Repository` builds typed,
    validated access for one document kind on top of it.
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        name: str,
    ) -> None:
        self._client = client
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    async def ensure_database(self) -> None:
        """Create the database if it does not already exist."""
        response = await self._client.put(f"/{self._name}")
        # 412 Precondition Failed means it already exists — the desired state.
        if response.status_code == httpx.codes.PRECONDITION_FAILED:
            return
        response.raise_for_status()

    async def ensure_index(
        self,
        *,
        name: str,
        fields: list[str],
    ) -> None:
        """Create a Mango index over `fields` if it does not already exist."""
        response = await self._client.post(
            url=f"/{self._name}/_index",
            json={"index": {"fields": fields}, "name": name, "type": "json"},
        )
        response.raise_for_status()

    async def get(self, id: str) -> dict[str, Any] | None:
        response = await self._client.get(f"/{self._name}/{id}")
        if response.status_code == httpx.codes.NOT_FOUND:
            return None
        response.raise_for_status()
        return response.json()

    async def save(self, id: str, doc: dict[str, Any]) -> str:
        """Write `doc` at `id` and return the new revision.

        Updating an existing document requires its current revision in
        `doc["_rev"]`; a stale or missing revision raises `DocumentConflict`.
        """
        response = await self._client.put(
            f"/{self._name}/{id}",
            json=doc,
        )
        if response.status_code == httpx.codes.CONFLICT:
            raise DocumentConflict(id)
        response.raise_for_status()
        return response.json()["rev"]

    async def delete(self, id: str, rev: str) -> None:
        """Delete the document at `id`, which must be at revision `rev`.

        A stale revision raises `DocumentConflict`.
        """
        response = await self._client.delete(
            f"/{self._name}/{id}",
            params={"rev": rev},
        )
        if response.status_code == httpx.codes.CONFLICT:
            raise DocumentConflict(id)
        response.raise_for_status()

    async def find(
        self,
        selector: dict[str, Any],
        *,
        sort: list[dict[str, str]] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        body: dict[str, Any] = {"selector": selector}
        if sort is not None:
            body["sort"] = sort
        if limit is not None:
            body["limit"] = limit

        response = await self._client.post(f"/{self._name}/_find", json=body)
        response.raise_for_status()
        return response.json()["docs"]

    async def changes(
        self,
        *,
        since: str = "0",
        selector: dict[str, Any] | None = None,
        include_docs: bool = True,
        heartbeat: int = 30_000,
    ) -> AsyncGenerator[Change]:
        """Stream the continuous `_changes` feed from `since` onwards.

        With `selector`, only matching documents are streamed — and deletions
        are dropped entirely, because a tombstone retains no fields for the
        selector to match. Consumers that must observe removal should model
        it as a flag on the document instead of deleting.

        The iterator ends only when the server closes the feed; consumers
        typically run it in a long-lived task.
        """
        params: dict[str, str] = {
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
                yield Change(
                    seq=str(row["seq"]),
                    id=row["id"],
                    deleted=deleted,
                    doc=None if deleted else row.get("doc"),
                )
