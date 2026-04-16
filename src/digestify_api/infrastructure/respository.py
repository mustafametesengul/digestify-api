from typing import Generic, TypeVar

from abc import ABC, abstractmethod

from digestify_api.infrastructure.aggregate import Aggregate


class OptimisticConcurrencyError(Exception):
    pass


T = TypeVar("T", bound=Aggregate)


class Repository(Generic[T], ABC):
    @abstractmethod
    async def register(self, name: str) -> None: ...

    @abstractmethod
    async def save(self, aggregate: T) -> None: ...

    @abstractmethod
    async def load(self, aggregate: T) -> None: ...
