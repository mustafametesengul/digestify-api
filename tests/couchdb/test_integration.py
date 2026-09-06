"""Tests against a real CouchDB server.

Skipped automatically unless a server is reachable at the configured URL;
start one with `docker compose up -d db`.
"""

import asyncio
from collections.abc import AsyncGenerator, AsyncIterator
from typing import Literal
from uuid import uuid4

import httpx
import pytest

from digestify_api.couchdb import (
    CouchDBSettings,
    Database,
    Document,
    DocumentConflict,
    Repository,
)

settings = CouchDBSettings()


def couchdb_is_running() -> bool:
    try:
        response = httpx.get(f"{settings.url}/_up", timeout=2.0)
    except httpx.TransportError:
        return False
    return response.status_code == httpx.codes.OK


pytestmark = pytest.mark.skipif(
    not couchdb_is_running(),
    reason=f"no CouchDB at {settings.url}; start one with `docker compose up -d db`",
)


class Item(Document):
    type: Literal["item"] = "item"
    name: str


class Other(Document):
    type: Literal["other"] = "other"


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        base_url=settings.url,
        auth=(settings.user, settings.password.get_secret_value()),
        timeout=httpx.Timeout(10.0, read=None),
    ) as client:
        yield client


@pytest.fixture
async def database(client: httpx.AsyncClient) -> AsyncIterator[Database]:
    database = Database(client, f"test-{uuid4().hex}")
    await database.ensure_database()
    yield database
    await client.delete(f"/{database.name}")


async def collect[T](feed: AsyncGenerator[T], count: int) -> list[T]:
    """Read `count` rows from a continuous feed, then close it."""
    rows: list[T] = []
    try:
        async with asyncio.timeout(15):
            async for row in feed:
                rows.append(row)
                if len(rows) == count:
                    break
    finally:
        await feed.aclose()
    return rows


async def test_ensure_database_is_idempotent(database: Database) -> None:
    await database.ensure_database()


async def test_document_lifecycle(database: Database) -> None:
    rev1 = await database.save("a", {"type": "item", "name": "widget"})

    doc = await database.get("a")
    assert doc is not None
    assert doc["_rev"] == rev1
    assert doc["name"] == "widget"

    rev2 = await database.save("a", {"_rev": rev1, "type": "item", "name": "gadget"})
    assert rev2 != rev1

    with pytest.raises(DocumentConflict):
        await database.save("a", {"_rev": rev1, "type": "item", "name": "stale"})

    await database.delete("a", rev2)
    assert await database.get("a") is None

    with pytest.raises(httpx.HTTPStatusError):
        await database.delete("a", rev2)


async def test_find_with_index(database: Database) -> None:
    await database.ensure_index(name="items_by_name", fields=["type", "name"])
    await database.save("a", {"type": "item", "name": "banana"})
    await database.save("b", {"type": "item", "name": "apple"})
    await database.save("c", {"type": "other"})

    docs = await database.find(
        {"type": "item"},
        sort=[{"type": "asc"}, {"name": "asc"}],
    )
    assert [doc["name"] for doc in docs] == ["apple", "banana"]

    docs = await database.find({"type": "item"}, limit=1)
    assert len(docs) == 1


@pytest.mark.parametrize(
    "id",
    [
        "a?b",
        "a#b",
        "a/b",
        "a%2Fb",
        "../other",
        ".",
        "..",
        "_design/example",
        "_local/example",
        "_design/a?b",
        "_local/a#b",
    ],
)
async def test_encoded_document_lifecycle(database: Database, id: str) -> None:
    await database.save("a", {"type": "item", "name": "untouched"})
    rev = await database.save(id, {"_id": id, "type": "item", "name": "original"})

    doc = await database.get(id)
    assert doc is not None
    assert doc["_id"] == id
    assert doc["_rev"] == rev

    doc["name"] = "updated"
    rev = await database.save(id, doc)
    updated = await database.get(id)
    assert updated is not None
    assert updated["name"] == "updated"

    await database.delete(id, rev)
    assert await database.get(id) is None
    untouched = await database.get("a")
    assert untouched is not None
    assert untouched["name"] == "untouched"


async def test_repository_find_across_pages(database: Database) -> None:
    items = Repository(Item, database)
    expected_ids = {f"item-{index:03d}" for index in range(105)}
    for id in sorted(expected_ids):
        await items.save(Item(id=id, name=id))
    await database.save("other", {"type": "other"})

    found = await items.find()
    assert len(found) == len(expected_ids)
    assert {item.id for item in found} == expected_ids

    limited = await items.find(limit=102)
    assert len(limited) == 102
    assert len({item.id for item in limited}) == 102
    assert {item.id for item in limited} <= expected_ids


async def test_changes_streams_saves_and_deletions(database: Database) -> None:
    await database.save("a", {"type": "item", "name": "widget"})
    rev = await database.save("b", {"type": "item", "name": "doomed"})
    await database.delete("b", rev)

    changes = {change.id: change for change in await collect(database.changes(), 2)}

    assert changes["a"].deleted is False
    assert changes["a"].doc is not None
    assert changes["a"].doc["name"] == "widget"

    assert changes["b"].deleted is True
    assert changes["b"].doc is None


async def test_changes_resumes_from_seq(database: Database) -> None:
    await database.save("a", {"type": "item", "name": "first"})
    [first] = await collect(database.changes(), 1)

    await database.save("b", {"type": "item", "name": "second"})
    [second] = await collect(database.changes(since=first.seq), 1)

    assert second.id == "b"


async def test_repository_round_trip(database: Database) -> None:
    items = Repository(Item, database)
    item = Item(id="a", name="widget")

    await items.save(item)
    assert item.rev is not None

    # The updated rev makes an immediate second save valid.
    item.name = "gadget"
    await items.save(item)

    loaded = await items.get("a")
    assert loaded == item

    await items.delete(item)
    assert await items.get("a") is None


async def test_repository_save_conflict(database: Database) -> None:
    items = Repository(Item, database)
    await items.save(Item(id="a", name="widget"))

    first = await items.get("a")
    second = await items.get("a")
    assert first is not None and second is not None

    first.name = "gadget"
    await items.save(first)

    second.name = "gizmo"
    with pytest.raises(DocumentConflict):
        await items.save(second)


async def test_repository_scopes_queries_to_kind(database: Database) -> None:
    await database.ensure_index(name="by_type", fields=["type"])
    items = Repository(Item, database)
    others = Repository(Other, database)

    await items.save(Item(id="a", name="widget"))
    await others.save(Other(id="b"))

    assert [item.id for item in await items.find()] == ["a"]
    assert await items.get("b") is None


async def test_repository_changes_only_sees_own_kind(database: Database) -> None:
    items = Repository(Item, database)
    others = Repository(Other, database)

    await others.save(Other(id="b"))
    await items.save(Item(id="a", name="widget"))

    [change] = await collect(items.changes(), 1)

    assert change.id == "a"
    assert change.doc == Item(id="a", rev=change.doc.rev, name="widget")
