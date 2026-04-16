from typing import TypeVar, override

from nats.errors import TimeoutError as NatsTimeoutError
from nats.js.client import JetStreamContext

from digestify_api.infrastructure.aggregate import Aggregate
from digestify_api.infrastructure.respository import Repository


T = TypeVar("T", bound=Aggregate)


class NATSRepository(Repository[T]):
    def __init__(
        self,
        js: JetStreamContext,
        subject_prefix: str,
    ) -> None:
        self._js = js
        self._subject_prefix = subject_prefix

    @override
    async def register(self, name: str) -> None:
        await self._js.add_stream(name=name, subjects=[f"{self._subject_prefix}.*"])

    @override
    async def save(self, aggregate: T) -> None:
        subject = f"{self._subject_prefix}.{aggregate._id}"

        events = aggregate._pending_events
        for event in events:
            await self._js.publish(
                subject,
                event.model_dump_json().encode("utf-8"),
            )

    @override
    async def load(self, aggregate: T) -> None:
        subject = f"{self._subject_prefix}.{aggregate._id}"

        events = []
        sub: JetStreamContext.PushSubscription | None = None
        try:
            pass
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

        for event_json in events:
            aggregate.apply_json(event_json)
