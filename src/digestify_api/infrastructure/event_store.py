from typing import Generic, Self, TypeVar
from uuid import UUID, uuid4

from nats.errors import TimeoutError as NatsTimeoutError
from nats.js.client import JetStreamContext
from pydantic import BaseModel, Field


class OptimisticConcurrencyError(Exception):
    pass


class Entity(BaseModel):
    id: int | UUID | str = Field(default_factory=uuid4)
    version: int = 0
    discarded: bool = False


T = TypeVar("T", bound=Entity)


class Event(BaseModel):
    entity_id: int | UUID | str
    entity_version: int


class Command(BaseModel):
    id: UUID = Field(default_factory=uuid4)


class EventStore(Generic[T]):
    def __init__(self, js: JetStreamContext, entity_class: type[T]) -> None:
        self._js = js
        self._entity_class = entity_class
        self._subject_prefix = entity_class.__name__.lower()

    async def register(self, name: str) -> None:
        await self._js.add_stream(name=name, subjects=[f"{self._subject_prefix}.*"])

    async def add_event(self, event: Event) -> None:
        subject = f"{self._subject_prefix}.{event.entity_id}"

        print(subject)

        await self._js.publish(
            subject,
            event.model_dump_json().encode("utf-8"),
        )

    async def load(self, entity_id: int | UUID | str) -> T | None:
        subject = f"{self._subject_prefix}.{entity_id}"

        events = []
        sub: JetStreamContext.PushSubscription | None = None
        try:
            sub = await self._js.subscribe(subject)
            while True:
                msg = await sub.next_msg(timeout=0.1)
                events.append(msg.data.decode("utf-8"))
        except NatsTimeoutError:
            pass
        finally:
            if sub is not None:
                await sub.unsubscribe()

        if not events:
            return None

        entity = self._entity_class.from_events_json(events)
        if entity.discarded:
            return None

        return entity
