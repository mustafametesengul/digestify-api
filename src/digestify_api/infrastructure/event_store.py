from uuid import UUID, uuid4

from nats.js.client import JetStreamContext
from nats.errors import TimeoutError as NatsTimeoutError

from pydantic import BaseModel, Field


class OptimisticConcurrencyError(Exception):
    pass


class Entity(BaseModel):
    id: int | UUID | str = Field(default_factory=uuid4)
    version: int = 0
    discarded: bool = False


class Event(BaseModel):
    entity_id: int | UUID | str
    entity_version: int


class Command(BaseModel):
    id: UUID = Field(default_factory=uuid4)


class EventStore:
    def __init__(self, js: JetStreamContext) -> None:
        self._js = js

    async def save(self, subject: str, event: Event) -> None:
        subject = f"{subject}.{event.entity_id}"

        await self._js.publish(
            subject,
            event.model_dump_json().encode("utf-8"),
        )

    async def load(self, subject: str, entity_id: int | UUID | str) -> list[str]:
        subject = f"{subject}.{entity_id}"

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

        return events
