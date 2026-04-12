from datetime import UTC, datetime
from typing import Callable, Generic, ParamSpec, Self, TypeVar, Concatenate
from uuid import UUID, uuid4

from nats.errors import TimeoutError as NatsTimeoutError
from nats.js.client import JetStreamContext
from pydantic import BaseModel, Field


class OptimisticConcurrencyError(Exception):
    pass


class Event(BaseModel):
    entity_id: int | UUID | str = Field(default_factory=uuid4)
    entity_version: int = 0


class Command(BaseModel):
    id: UUID = Field(default_factory=uuid4)


class Entity(BaseModel):
    id: int | UUID | str = Field(default_factory=uuid4)
    version: int = 0
    discarded: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # @abstractmethod
    # def apply(self, event: Event) -> None:
    #     handler = _handlers.get(type(self), {}).get(event.type)
    #     if handler is None:
    #         raise ValueError(f"No handler for event type {event.type} on entity {type(self).__name__}")
    #     handler(self, event)


P = ParamSpec("P")
R = TypeVar("R")
T = TypeVar("T", bound=Entity)
E = TypeVar("E", bound=Event)


_handlers: dict[type[Entity], dict[str, Callable[[Entity, Event], None]]] = {}


def handler(
    func: Callable[[T, E], R],
) -> Callable[[T, E], R]:
    return func


def classhandler(
    func: Callable[[type[T], E], T],
) -> Callable[[type[T], E], T]:
    return func


def command(
    func: Callable[Concatenate[T, P], Event],
) -> Callable[Concatenate[T, P], None]:
    def wrapper(entity: T, *args: P.args, **kwargs: P.kwargs) -> None:
        event = func(entity, *args, **kwargs)
        event.entity_id = entity.id
        event.entity_version = entity.version + 1
        # entity.apply(event)
        return None

    return wrapper


def classcommand(
    func: Callable[Concatenate[type[T], P], Event],
) -> Callable[Concatenate[type[T], P], T]:
    """
    A version of the `command` decorator designed to work on class methods
    (e.g., for creating a new entity). It sets the initial entity context.
    """

    def wrapper(cls: type[T], *args: P.args, **kwargs: P.kwargs) -> T:
        event = func(cls, *args, **kwargs)
        # For a creation event, the version starts at 1
        print("Creating entity with event:", event)
        entity = cls()
        return entity

    return wrapper


class EventStore(Generic[T]):
    def __init__(self, js: JetStreamContext, entity_class: type[T]) -> None:
        self._js = js
        self._entity_class = entity_class
        self._subject_prefix = entity_class.__name__.lower()

    async def register(self, name: str) -> None:
        await self._js.add_stream(name=name, subjects=[f"{self._subject_prefix}.*"])

    async def add_event(self, event: Event) -> None:
        subject = f"{self._subject_prefix}.{event.entity_id}"

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

        # entity = self._entity_class.from_events_json(events)
        # if entity.discarded:
        #     return None

        # return entity

        return None
