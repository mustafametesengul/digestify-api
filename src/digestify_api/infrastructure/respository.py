from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from pydantic import BaseModel, JsonValue

from digestify_api.infrastructure.aggregate import Aggregate


class OptimisticConcurrencyError(Exception):
    pass


A = TypeVar("A", bound=Aggregate)


class Repository(Generic[A], ABC):
    @abstractmethod
    async def _save_events(self, events: list[str]) -> None: ...

    @abstractmethod
    async def _load_events(self, aggregate_id: str) -> list[str]: ...

    async def save(self, aggregate: A) -> None:
        events = [event.model_dump_json() for event in aggregate._pending_events]
        await self._save_events(events)
        events.clear()

    async def load(self, aggregate: A) -> None:
        events = await self._load_events(aggregate._id)
        for event_json in events:
            aggregate.apply_json(event_json)
