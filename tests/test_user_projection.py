import json
from typing import Any, cast

import httpx
import pytest
from digestify_api.news.checkpoint import ProjectionCheckpoint
from digestify_api.news.user import User

from digestify_api.infrastructure.database import Document, DocumentRepository, T
from digestify_api.news.user_projection import CHECKPOINT_ID, UserProjection


class InMemoryRepository(DocumentRepository[T]):
    def __init__(self, document_type: type[T]) -> None:
        self._document_type = document_type
        self._documents: dict[str, str] = {}

    async def get(self, id: str) -> T | None:
        stored = self._documents.get(id)
        if stored is None:
            return None
        return self._document_type.model_validate_json(stored)

    async def save(self, document: Document) -> None:
        self._documents[document.id] = document.model_dump_json(by_alias=True)

    async def find(
        self,
        selector: dict[str, Any],
        *,
        sort: list[dict[str, str]] | None = None,
        limit: int | None = None,
    ) -> list[T]:
        matches = [
            doc
            for doc in (
                self._document_type.model_validate_json(stored)
                for stored in self._documents.values()
            )
            if all(getattr(doc, key) == value for key, value in selector.items())
        ]
        if sort:
            field, direction = next(iter(sort[0].items()))
            matches.sort(
                key=lambda doc: getattr(doc, field), reverse=direction == "desc"
            )
        if limit is not None:
            matches = matches[:limit]
        return matches


def change_line(seq: str, user_id: str, **doc: object) -> str:
    return json.dumps(
        {
            "seq": seq,
            "id": user_id,
            "changes": [{"rev": "1-abc"}],
            "doc": {"_id": user_id, "type": "user", **doc},
        }
    )


@pytest.fixture
def users() -> InMemoryRepository[User]:
    return InMemoryRepository(User)


@pytest.fixture
def checkpoints() -> InMemoryRepository[ProjectionCheckpoint]:
    return InMemoryRepository(ProjectionCheckpoint)


@pytest.fixture
def projection(
    users: InMemoryRepository[User],
    checkpoints: InMemoryRepository[ProjectionCheckpoint],
) -> UserProjection:
    return UserProjection(
        client=cast(httpx.AsyncClient, None), users=users, checkpoints=checkpoints
    )


async def test_user_change_creates_projected_user(
    projection: UserProjection, users: InMemoryRepository[User]
) -> None:
    checkpoint = ProjectionCheckpoint.start(CHECKPOINT_ID)

    await projection._apply_line(
        change_line("1", "user-1", is_deleted=False), checkpoint
    )

    user = await users.get("user-1")
    assert user is not None
    assert user.is_active()


async def test_apply_is_idempotent_on_replay(
    projection: UserProjection, users: InMemoryRepository[User]
) -> None:
    checkpoint = ProjectionCheckpoint.start(CHECKPOINT_ID)
    line = change_line("7", "user-1", is_deleted=False)

    await projection._apply_line(line, checkpoint)
    await projection._apply_line(line, checkpoint)  # crash-resume replay

    assert len(users._documents) == 1
    user = await users.get("user-1")
    assert user is not None and user.is_active()


async def test_soft_delete_propagates(
    projection: UserProjection, users: InMemoryRepository[User]
) -> None:
    checkpoint = ProjectionCheckpoint.start(CHECKPOINT_ID)

    await projection._apply_line(
        change_line("1", "user-1", is_deleted=False), checkpoint
    )
    await projection._apply_line(
        change_line("2", "user-1", is_deleted=True), checkpoint
    )

    user = await users.get("user-1")
    assert user is not None and not user.is_active()


async def test_tombstone_marks_user_deleted(
    projection: UserProjection, users: InMemoryRepository[User]
) -> None:
    checkpoint = ProjectionCheckpoint.start(CHECKPOINT_ID)
    line = json.dumps(
        {
            "seq": "3",
            "id": "user-1",
            "changes": [{"rev": "2-def"}],
            "deleted": True,
            "doc": {"_id": "user-1", "_rev": "2-def", "_deleted": True},
        }
    )

    await projection._apply_line(line, checkpoint)

    user = await users.get("user-1")
    assert user is not None and not user.is_active()


async def test_checkpoint_advances_only_after_apply(
    projection: UserProjection,
    checkpoints: InMemoryRepository[ProjectionCheckpoint],
) -> None:
    checkpoint = ProjectionCheckpoint.start(CHECKPOINT_ID)

    await projection._apply_line(change_line("42", "user-1"), checkpoint)

    stored = await checkpoints.get(CHECKPOINT_ID)
    assert stored is not None and stored.last_seq == "42"


async def test_heartbeat_and_final_rows_are_ignored(
    projection: UserProjection,
    users: InMemoryRepository[User],
    checkpoints: InMemoryRepository[ProjectionCheckpoint],
) -> None:
    checkpoint = ProjectionCheckpoint.start(CHECKPOINT_ID)

    await projection._apply_line(
        json.dumps({"last_seq": "99", "pending": 0}), checkpoint
    )

    assert users._documents == {}
    assert await checkpoints.get(CHECKPOINT_ID) is None
    assert checkpoint.last_seq == "0"
