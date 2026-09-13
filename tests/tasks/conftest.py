import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

from digestify_api.couchdb import Client
from digestify_api.tasks import Service


class InMemoryCouch:
    def __init__(self) -> None:
        self.databases: dict[str, dict[str, dict[str, Any]]] = {"tasks": {}}
        self.requests: list[tuple[str, str]] = []
        self.revision = 0
        self.next_write_status = 201
        self.read_barrier: asyncio.Barrier | None = None
        self.barrier_reads = 0

    @property
    def docs(self) -> dict[str, dict[str, Any]]:
        return self.databases["tasks"]

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.requests.append((request.method, path))
        parts = path.strip("/").split("/", 1)
        docs = self.databases.setdefault(parts[0], {})
        if len(parts) == 1:
            return httpx.Response(201, json={"ok": True})
        identity = parts[1]
        if path.endswith("/_find"):
            body = json.loads(request.content)
            matches = [
                doc
                for doc in docs.values()
                if self.matches(doc, body["selector"])
            ]
            offset = int(body.get("bookmark", "0"))
            end = offset + body["limit"]
            return httpx.Response(
                200, json={"docs": matches[offset:end], "bookmark": str(end)}
            )
        if path.endswith("/_changes"):
            return httpx.Response(200, content='{"last_seq":"0"}\n')
        if path.endswith("/_index"):
            return httpx.Response(201, json={"ok": True})
        if request.method == "GET":
            doc = docs.get(identity)
            response = (
                httpx.Response(200, json=doc) if doc else httpx.Response(404)
            )
            if self.read_barrier is not None and self.barrier_reads < 2:
                self.barrier_reads += 1
                await self.read_barrier.wait()
            return response
        if request.method == "PUT":
            body = json.loads(request.content)
            existing = docs.get(identity)
            if body.get("_rev") != (existing["_rev"] if existing else None):
                return httpx.Response(409)
            status, self.next_write_status = self.next_write_status, 201
            if status in (201, 202):
                self.revision += 1
                revision = f"{self.revision}-test"
                docs[identity] = {
                    **body,
                    "_id": identity,
                    "_rev": revision,
                }
                return httpx.Response(status, json={"rev": revision})
            return httpx.Response(status)
        raise AssertionError(
            f"Unexpected request: {request.method} {request.url}"
        )

    @staticmethod
    def matches(document: dict[str, Any], selector: dict[str, Any]) -> bool:
        for field, expected in selector.items():
            actual = document.get(field)
            if isinstance(expected, dict):
                if "$in" in expected and actual not in expected["$in"]:
                    return False
                if "$lte" in expected and (
                    actual is None or actual > expected["$lte"]
                ):
                    return False
            elif actual != expected:
                return False
        return True


@dataclass
class Clock:
    now: datetime = datetime(2026, 1, 1, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def couch() -> InMemoryCouch:
    return InMemoryCouch()


@pytest.fixture
async def service(
    couch: InMemoryCouch, clock: Clock
) -> AsyncIterator[Service]:
    async with httpx.AsyncClient(
        base_url="http://couch", transport=httpx.MockTransport(couch)
    ) as client:
        yield Service(Client(client), clock=clock)
