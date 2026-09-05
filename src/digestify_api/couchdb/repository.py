from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any, get_args

from pydantic import BaseModel, ConfigDict, Field

from digestify_api.couchdb.database import Database


class Document(BaseModel):
    """A persistable document identified by `id` and a CouchDB revision.

    Every document carries a `type` discriminator so a single database can
    hold multiple document kinds. Subclasses pin it to a single-valued
    `Literal`, for example ``type: Literal["user"] = "user"``.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(validation_alias="_id", serialization_alias="_id")
    rev: str | None = Field(
        default=None,
        validation_alias="_rev",
        serialization_alias="_rev",
    )
    type: str


@dataclass(slots=True, frozen=True)
class DocumentChange[T: Document]:
    """A typed row from the `_changes` feed; see `Repository.changes`."""

    seq: str
    id: str
    doc: T


class Repository[T: Document]:
    """Typed access to one document kind stored in a `Database`.

    Every operation validates documents against `model_type` and scopes
    reads to its `type` discriminator, so repositories for different kinds
    can safely share a single database.
    """

    def __init__(self, model_type: type[T], database: Database) -> None:
        self._model_type = model_type
        self._database = database
        self._type = _document_type(model_type)

    async def get(self, id: str) -> T | None:
        """The document at `id`, or ``None`` if absent or of another kind."""
        doc = await self._database.get(id)
        if doc is None or doc.get("type") != self._type:
            return None
        return self._model_type.model_validate(doc)

    async def save(self, document: T) -> None:
        """Persist `document` and update its `rev` to the stored revision.

        Saving over a concurrent update raises `DocumentConflict`; reload the
        document, reapply the change, and save again.
        """
        body: dict[str, Any] = document.model_dump(by_alias=True, mode="json")
        if body["_rev"] is None:
            del body["_rev"]
        document.rev = await self._database.save(id=document.id, doc=body)

    async def delete(self, document: T) -> None:
        """Delete `document` at its current revision.

        A stale revision raises `DocumentConflict`. Deletions are invisible
        to `changes`; prefer an ``is_deleted``-style flag when feed consumers
        must observe removal.
        """
        if document.rev is None:
            raise ValueError("Cannot delete a document that was never saved.")
        await self._database.delete(document.id, document.rev)

    async def find(
        self,
        selector: dict[str, Any] | None = None,
        *,
        sort: list[dict[str, str]] | None = None,
        limit: int | None = None,
    ) -> list[T]:
        """Documents of this kind matching `selector` (all of them if omitted).

        The `type` discriminator is added to the selector automatically, so
        indexes backing these queries should lead with the `type` field.
        """
        docs = await self._database.find(
            {**(selector or {}), "type": self._type},
            sort=sort,
            limit=limit,
        )
        return [self._model_type.model_validate(doc) for doc in docs]

    async def changes(self, since: str = "0") -> AsyncGenerator[DocumentChange[T]]:
        """Stream changes to documents of this kind from `since` onwards.

        Filtering happens server-side on the `type` discriminator. Deletions
        never appear (a tombstone retains no fields to match); model removal
        as a flag on the document if consumers must see it.
        """
        async for change in self._database.changes(
            since=since,
            selector={"type": self._type},
        ):
            if change.doc is None:
                continue
            yield DocumentChange(
                seq=change.seq,
                id=change.id,
                doc=self._model_type.model_validate(change.doc),
            )


def _document_type(model_type: type[Document]) -> str:
    """The `type` discriminator value `model_type` is pinned to."""
    field = model_type.model_fields["type"]
    if isinstance(field.default, str):
        return field.default
    literal_values = get_args(field.annotation)
    if len(literal_values) == 1 and isinstance(literal_values[0], str):
        return literal_values[0]
    raise TypeError(
        f"{model_type.__name__} must pin `type` to a single value, "
        'e.g. `type: Literal["user"] = "user"`.'
    )
