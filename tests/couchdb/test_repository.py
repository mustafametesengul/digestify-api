import json
from typing import Literal

import httpx
import pytest

from digestify_api.couchdb import Database, Document, DocumentConflict, Repository
from tests.couchdb.conftest import FakeServer


class Item(Document):
    type: Literal["item"] = "item"
    name: str


class ItemWithoutDefault(Document):
    type: Literal["item"]
    name: str


@pytest.fixture
def repository(database: Database) -> Repository[Item]:
    return Repository(Item, database)


async def test_get_validates_document(
    server: FakeServer, repository: Repository[Item]
) -> None:
    server.enqueue(
        httpx.Response(
            200, json={"_id": "a", "_rev": "1-x", "type": "item", "name": "widget"}
        )
    )

    item = await repository.get("a")

    assert item == Item(id="a", rev="1-x", name="widget")


async def test_get_returns_none_when_missing(
    server: FakeServer, repository: Repository[Item]
) -> None:
    server.enqueue(httpx.Response(404, json={"error": "not_found"}))

    assert await repository.get("a") is None


async def test_get_returns_none_for_other_document_kind(
    server: FakeServer, repository: Repository[Item]
) -> None:
    server.enqueue(
        httpx.Response(200, json={"_id": "a", "_rev": "1-x", "type": "user"})
    )

    assert await repository.get("a") is None


async def test_save_new_document_omits_rev(
    server: FakeServer, repository: Repository[Item]
) -> None:
    server.enqueue(httpx.Response(201, json={"ok": True, "id": "a", "rev": "1-x"}))
    item = Item(id="a", name="widget")

    await repository.save(item)

    assert json.loads(server.request.content) == {
        "_id": "a",
        "type": "item",
        "name": "widget",
    }
    assert item.rev == "1-x"


async def test_save_existing_document_sends_rev_and_updates_it(
    server: FakeServer, repository: Repository[Item]
) -> None:
    server.enqueue(httpx.Response(201, json={"ok": True, "id": "a", "rev": "2-y"}))
    item = Item(id="a", rev="1-x", name="widget")

    await repository.save(item)

    assert json.loads(server.request.content)["_rev"] == "1-x"
    assert item.rev == "2-y"


async def test_save_conflict_leaves_rev_untouched(
    server: FakeServer, repository: Repository[Item]
) -> None:
    server.enqueue(httpx.Response(409, json={"error": "conflict"}))
    item = Item(id="a", rev="1-x", name="widget")

    with pytest.raises(DocumentConflict):
        await repository.save(item)

    assert item.rev == "1-x"


async def test_delete_sends_current_revision(
    server: FakeServer, repository: Repository[Item]
) -> None:
    server.enqueue(httpx.Response(200, json={"ok": True}))

    await repository.delete(Item(id="a", rev="2-y", name="widget"))

    assert server.request.method == "DELETE"
    assert server.request.url.path == "/things/a"
    assert server.request.url.params["rev"] == "2-y"


async def test_delete_rejects_unsaved_document(
    server: FakeServer, repository: Repository[Item]
) -> None:
    with pytest.raises(ValueError):
        await repository.delete(Item(id="a", name="widget"))

    assert server.requests == []


async def test_find_scopes_selector_to_document_kind(
    server: FakeServer, repository: Repository[Item]
) -> None:
    server.enqueue(
        httpx.Response(
            200,
            json={
                "docs": [{"_id": "a", "_rev": "1-x", "type": "item", "name": "widget"}]
            },
        )
    )

    items = await repository.find({"name": "widget"}, limit=5)

    assert items == [Item(id="a", rev="1-x", name="widget")]
    assert json.loads(server.request.content) == {
        "selector": {"name": "widget", "type": "item"},
        "limit": 5,
    }


async def test_find_without_selector_matches_whole_kind(
    server: FakeServer, repository: Repository[Item]
) -> None:
    server.enqueue(httpx.Response(200, json={"docs": []}))

    await repository.find()

    assert json.loads(server.request.content) == {"selector": {"type": "item"}}


async def test_find_ignores_caller_type_override(
    server: FakeServer, repository: Repository[Item]
) -> None:
    server.enqueue(httpx.Response(200, json={"docs": []}))

    await repository.find({"type": "user"})

    assert json.loads(server.request.content)["selector"] == {"type": "item"}


async def test_changes_filters_server_side_and_validates(
    server: FakeServer, repository: Repository[Item]
) -> None:
    server.enqueue(
        httpx.Response(
            200,
            content=(
                '{"seq": "1-a", "id": "a", "changes": [{"rev": "1-x"}],'
                ' "doc": {"_id": "a", "_rev": "1-x", "type": "item", "name": "widget"}}\n'
                '{"last_seq": "1-a", "pending": 0}\n'
            ).encode(),
        )
    )

    changes = [change async for change in repository.changes(since="0")]

    assert len(changes) == 1
    assert changes[0].seq == "1-a"
    assert changes[0].id == "a"
    assert changes[0].doc == Item(id="a", rev="1-x", name="widget")

    params = server.request.url.params
    assert params["filter"] == "_selector"
    assert json.loads(server.request.content) == {"selector": {"type": "item"}}


async def test_changes_skips_rows_without_documents(
    server: FakeServer, repository: Repository[Item]
) -> None:
    server.enqueue(
        httpx.Response(
            200,
            content=(
                '{"seq": "2-b", "id": "b", "changes": [{"rev": "2-y"}], "deleted": true}\n'
            ).encode(),
        )
    )

    changes = [change async for change in repository.changes()]

    assert changes == []


async def test_changes_skips_rows_with_mismatched_document_kind(
    server: FakeServer, repository: Repository[Item]
) -> None:
    server.enqueue(
        httpx.Response(
            200,
            content=(
                '{"seq": "1-a", "id": "a", "changes": [{"rev": "1-x"}],'
                ' "doc": {"_id": "a", "_rev": "1-x", "type": "user"}}\n'
            ).encode(),
        )
    )

    changes = [change async for change in repository.changes()]

    assert changes == []


def test_document_kind_from_literal_default(database: Database) -> None:
    assert Repository(Item, database)._type == "item"


def test_document_kind_from_literal_without_default(database: Database) -> None:
    assert Repository(ItemWithoutDefault, database)._type == "item"


def test_document_kind_requires_single_pinned_value(database: Database) -> None:
    class Unpinned(Document):
        pass

    class MultiValued(Document):
        type: Literal["a", "b"]

    class MultiValuedWithDefault(Document):
        type: Literal["a", "b"] = "a"

    class StrWithDefault(Document):
        type: str = "a"

    with pytest.raises(TypeError):
        Repository(Unpinned, database)
    with pytest.raises(TypeError):
        Repository(MultiValued, database)
    with pytest.raises(TypeError):
        Repository(MultiValuedWithDefault, database)
    with pytest.raises(TypeError):
        Repository(StrWithDefault, database)
