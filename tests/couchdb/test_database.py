import json

import httpx
import pytest

from digestify_api.couchdb import Database, DocumentConflict
from tests.couchdb.conftest import FakeServer


async def test_ensure_database_creates(server: FakeServer, database: Database) -> None:
    server.enqueue(httpx.Response(201, json={"ok": True}))

    await database.ensure_database()

    assert server.request.method == "PUT"
    assert server.request.url.path == "/things"


async def test_ensure_database_tolerates_existing(
    server: FakeServer, database: Database
) -> None:
    server.enqueue(httpx.Response(412))

    await database.ensure_database()


async def test_ensure_database_raises_on_error(
    server: FakeServer, database: Database
) -> None:
    server.enqueue(httpx.Response(500))

    with pytest.raises(httpx.HTTPStatusError):
        await database.ensure_database()


async def test_ensure_index(server: FakeServer, database: Database) -> None:
    server.enqueue(httpx.Response(200, json={"result": "created"}))

    await database.ensure_index(name="things_by_email", fields=["type", "email"])

    assert server.request.method == "POST"
    assert server.request.url.path == "/things/_index"
    assert json.loads(server.request.content) == {
        "index": {"fields": ["type", "email"]},
        "name": "things_by_email",
        "type": "json",
    }


async def test_get_returns_document(server: FakeServer, database: Database) -> None:
    server.enqueue(httpx.Response(200, json={"_id": "a", "_rev": "1-x"}))

    doc = await database.get("a")

    assert doc == {"_id": "a", "_rev": "1-x"}
    assert server.request.method == "GET"
    assert server.request.url.path == "/things/a"


async def test_get_returns_none_when_missing(
    server: FakeServer, database: Database
) -> None:
    server.enqueue(httpx.Response(404, json={"error": "not_found"}))

    assert await database.get("a") is None


async def test_get_raises_on_error(server: FakeServer, database: Database) -> None:
    server.enqueue(httpx.Response(500))

    with pytest.raises(httpx.HTTPStatusError):
        await database.get("a")


async def test_save_returns_new_revision(
    server: FakeServer, database: Database
) -> None:
    server.enqueue(httpx.Response(201, json={"ok": True, "id": "a", "rev": "2-y"}))

    rev = await database.save("a", {"_id": "a", "_rev": "1-x", "type": "item"})

    assert rev == "2-y"
    assert server.request.method == "PUT"
    assert server.request.url.path == "/things/a"
    assert json.loads(server.request.content) == {
        "_id": "a",
        "_rev": "1-x",
        "type": "item",
    }


async def test_save_raises_document_conflict(
    server: FakeServer, database: Database
) -> None:
    server.enqueue(httpx.Response(409, json={"error": "conflict"}))

    with pytest.raises(DocumentConflict):
        await database.save("a", {"_id": "a"})


async def test_delete_sends_revision(server: FakeServer, database: Database) -> None:
    server.enqueue(httpx.Response(200, json={"ok": True}))

    await database.delete("a", "2-y")

    assert server.request.method == "DELETE"
    assert server.request.url.path == "/things/a"
    assert server.request.url.params["rev"] == "2-y"


async def test_delete_raises_document_conflict(
    server: FakeServer, database: Database
) -> None:
    server.enqueue(httpx.Response(409, json={"error": "conflict"}))

    with pytest.raises(DocumentConflict):
        await database.delete("a", "1-x")


async def test_find_sends_minimal_body(server: FakeServer, database: Database) -> None:
    server.enqueue(httpx.Response(200, json={"docs": []}))

    docs = await database.find({"type": "item"})

    assert docs == []
    assert server.request.url.path == "/things/_find"
    assert json.loads(server.request.content) == {"selector": {"type": "item"}}


async def test_find_sends_sort_and_limit(
    server: FakeServer, database: Database
) -> None:
    server.enqueue(httpx.Response(200, json={"docs": [{"_id": "a"}]}))

    docs = await database.find(
        {"type": "item"},
        sort=[{"type": "asc"}, {"email": "asc"}],
        limit=10,
    )

    assert docs == [{"_id": "a"}]
    assert json.loads(server.request.content) == {
        "selector": {"type": "item"},
        "sort": [{"type": "asc"}, {"email": "asc"}],
        "limit": 10,
    }


def changes_feed(*rows: str) -> httpx.Response:
    return httpx.Response(200, content="\n".join(rows).encode())


async def test_changes_parses_rows(server: FakeServer, database: Database) -> None:
    server.enqueue(
        changes_feed(
            '{"seq": "1-a", "id": "a", "changes": [{"rev": "1-x"}],'
            ' "doc": {"_id": "a", "_rev": "1-x", "type": "item"}}',
            "",  # heartbeat keep-alive
            '{"seq": "2-b", "id": "b", "changes": [{"rev": "2-y"}], "deleted": true,'
            ' "doc": {"_id": "b", "_rev": "2-y", "_deleted": true}}',
            '{"last_seq": "2-b", "pending": 0}',
        )
    )

    changes = [change async for change in database.changes()]

    assert len(changes) == 2

    assert changes[0].seq == "1-a"
    assert changes[0].id == "a"
    assert changes[0].deleted is False
    assert changes[0].doc == {"_id": "a", "_rev": "1-x", "type": "item"}

    # Tombstones surface as deletions with no document body.
    assert changes[1].seq == "2-b"
    assert changes[1].id == "b"
    assert changes[1].deleted is True
    assert changes[1].doc is None


async def test_changes_parses_integer_seq(
    server: FakeServer, database: Database
) -> None:
    server.enqueue(
        changes_feed(
            '{"seq": 1, "id": "a", "changes": [{"rev": "1-x"}],'
            ' "doc": {"_id": "a", "_rev": "1-x", "type": "item"}}',
        )
    )

    [change] = [change async for change in database.changes()]

    assert change.seq == "1"
    assert isinstance(change.seq, str)


async def test_changes_request_without_selector(
    server: FakeServer, database: Database
) -> None:
    server.enqueue(changes_feed())

    [change async for change in database.changes(since="5-x")]

    params = server.request.url.params
    assert server.request.method == "POST"
    assert server.request.url.path == "/things/_changes"
    assert params["feed"] == "continuous"
    assert params["since"] == "5-x"
    assert params["include_docs"] == "true"
    assert params["heartbeat"] == "30000"
    assert "filter" not in params
    assert json.loads(server.request.content) == {}


async def test_changes_request_with_selector(
    server: FakeServer, database: Database
) -> None:
    server.enqueue(changes_feed())

    [
        change
        async for change in database.changes(
            selector={"type": "item"},
            include_docs=False,
            heartbeat=5_000,
        )
    ]

    params = server.request.url.params
    assert params["filter"] == "_selector"
    assert params["include_docs"] == "false"
    assert params["heartbeat"] == "5000"
    assert json.loads(server.request.content) == {"selector": {"type": "item"}}


async def test_changes_raises_on_error(server: FakeServer, database: Database) -> None:
    server.enqueue(httpx.Response(400, json={"error": "bad_request"}))

    with pytest.raises(httpx.HTTPStatusError):
        [change async for change in database.changes()]
