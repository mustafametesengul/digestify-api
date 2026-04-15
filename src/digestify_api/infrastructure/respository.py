from typing import Generic, TypeVar, get_args
from uuid import UUID

from nats.errors import TimeoutError as NatsTimeoutError
from nats.js.client import JetStreamContext

from digestify_api.infrastructure.aggregate import Aggregate


class OptimisticConcurrencyError(Exception):
    pass


T = TypeVar("T", bound=Aggregate)


class Repository(Generic[T]):
    def __init__(self, js: JetStreamContext, entity_class: type[T]) -> None:
        self._js = js
        self._entity_class = entity_class
        self._subject_prefix = entity_class.__name__.lower()
        
        self._state_class = None
        for base in getattr(entity_class, "__orig_bases__", []):
            if getattr(base, "__origin__", None) is Aggregate:
                args = get_args(base)
                if args:
                    self._state_class = args[0]
                break

    async def register(self, name: str) -> None:
        await self._js.add_stream(name=name, subjects=[f"{self._subject_prefix}.*"])

    async def save(self, aggregate: T) -> None:
        subject = f"{self._subject_prefix}.{aggregate._id}"

        events = aggregate._pending_events
        for event in events:
            await self._js.publish(
                subject,
                event.model_dump_json().encode("utf-8"),
            )

    async def load(self, id: int | UUID | str) -> T | None:
        subject = f"{self._subject_prefix}.{id}"

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

        aggregate = self._entity_class(id=id)
        for event_json in events:
            aggregate.apply_json(event_json)

        return aggregate
