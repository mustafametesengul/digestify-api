import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

from digestify_api.couchdb import Database
from digestify_api.tasks import TaskService


class InMemoryCouch:
    def __init__(self) -> None:
        self.docs: dict[str, dict[str, Any]] = {}
        self.revision = 0
        self.next_write_status = 201
        self.read_barrier: asyncio.Barrier | None = None
        self.barrier_reads = 0

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/_find"):
            body = json.loads(request.content)
            docs = [
                doc for doc in self.docs.values() if self.matches(doc, body["selector"])
            ]
            offset = int(body.get("bookmark", "0"))
            end = offset + body["limit"]
            return httpx.Response(
                200, json={"docs": docs[offset:end], "bookmark": str(end)}
            )
        if path.endswith("/_changes"):
            return httpx.Response(200, content='{"last_seq":"0"}\n')
        if path.endswith("/_index") or path == "/tasks":
            return httpx.Response(201, json={"ok": True})
        identity = path.removeprefix("/tasks/")
        if request.method == "GET":
            doc = self.docs.get(identity)
            response = httpx.Response(200, json=doc) if doc else httpx.Response(404)
            if self.read_barrier is not None and self.barrier_reads < 2:
                self.barrier_reads += 1
                await self.read_barrier.wait()
            return response
        if request.method == "PUT":
            body = json.loads(request.content)
            existing = self.docs.get(identity)
            if body.get("_rev") != (existing["_rev"] if existing else None):
                return httpx.Response(409)
            status, self.next_write_status = self.next_write_status, 201
            if status in (201, 202):
                self.revision += 1
                revision = f"{self.revision}-test"
                self.docs[identity] = {**body, "_id": identity, "_rev": revision}
                return httpx.Response(status, json={"rev": revision})
            return httpx.Response(status)
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    @staticmethod
    def matches(document: dict[str, Any], selector: dict[str, Any]) -> bool:
        for field, expected in selector.items():
            actual = document.get(field)
            if isinstance(expected, dict):
                if "$in" in expected and actual not in expected["$in"]:
                    return False
                if "$lte" in expected and (actual is None or actual > expected["$lte"]):
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
async def service(couch: InMemoryCouch, clock: Clock) -> AsyncIterator[TaskService]:
    async with httpx.AsyncClient(
        base_url="http://couch", transport=httpx.MockTransport(couch)
    ) as client:
        yield TaskService(Database(client, "tasks"), clock=clock)
