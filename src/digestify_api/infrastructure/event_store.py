from uuid import UUID

from redis.asyncio import Redis

from pydantic import BaseModel


class OptimisticConcurrencyError(Exception):
    pass


class Entity(BaseModel):
    id: UUID
    version: int = 0


class Event(BaseModel):
    entity_id: UUID
    entity_version: int


class Command(BaseModel):
    pass


class EventStore:
    def __init__(self, redis: Redis, namespace: str = "users"):
        self._redis = redis
        self._namespace = namespace

    async def save(self, event: Event) -> None:
        stream_key = f"{self._namespace}:events:{{{event.entity_id}}}"

        await self._redis.xadd(
            name=stream_key,
            id=f"0-{event.entity_version}",
            fields={"event": event.model_dump_json()},
        )

    async def load(self, entity_id: UUID) -> list[str]:
        stream_key = f"{self._namespace}:events:{{{entity_id}}}"

        events_data = await self._redis.xrange(stream_key, count=1000)
        events = []
        for _, fields in events_data:
            event_binary = fields[b"event"]
            event_json = event_binary.decode("utf-8")
            events.append(event_json)

        return events
