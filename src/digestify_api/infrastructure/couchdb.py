from abc import ABC, abstractmethod
from typing import Generic, TypeVar

import httpx
from pydantic import BaseModel, ConfigDict, Field


class Document(BaseModel):
    """A persistable document identified by `id` and a CouchDB revision."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(validation_alias="_id", serialization_alias="_id")
    rev: str | None = Field(
        default=None,
        validation_alias="_rev",
        serialization_alias="_rev",
    )


class DocumentConflict(Exception):
    pass


T = TypeVar("T", bound=Document)


class DocumentRepository(ABC, Generic[T]):
    @abstractmethod
    async def get(self, id: str) -> T | None: ...

    @abstractmethod
    async def save(self, document: T) -> None: ...


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


async def ensure_database(client: httpx.AsyncClient, name: str) -> None:
    response = await client.put(f"/{name}")
    # 201 Created on first run, 412 Precondition Failed if it already exists.
    if response.status_code in (httpx.codes.CREATED, httpx.codes.PRECONDITION_FAILED):
        return
    response.raise_for_status()
