from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from digestify_api.infrastructure.aggregate import Aggregate


class OptimisticConcurrencyError(Exception):
    pass


A = TypeVar("A", bound=Aggregate)


class Repository(Generic[A], ABC):
    @abstractmethod
    async def save(self, aggregate: A) -> None: ...

    @abstractmethod
    async def load(self, aggregate: A) -> None: ...
