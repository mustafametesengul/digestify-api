from datetime import datetime, UTC
from typing import TypeVar, Generic

from pymongo.asynchronous.collection import AsyncCollection
from pymongo.errors import DuplicateKeyError
from uuid import UUID

from digestify_api.infrastructure.entity import Entity
from digestify_api.infrastructure.message_broker import MessageBroker

T = TypeVar("T", bound=Entity)


class ConcurrencyError(Exception):
    pass


class Repository(Generic[T]):
    def __init__(
        self,
        collection: AsyncCollection,
        messages_collection: AsyncCollection,
        processed_messages_collection: AsyncCollection,
        entity_class: type[T],
        message_broker: MessageBroker,
    ) -> None:
        self._collection = collection
        self._messages_collection = messages_collection
        self._processed_messages_collection = processed_messages_collection

        self._entity_class = entity_class
        self._message_broker = message_broker

    async def save(self, entity: T) -> None:
        expected_version = entity.version
        entity.version += 1
        entity.updated_at = datetime.now(UTC)

        document = entity.model_dump()
        document.pop("_id", None)

        try:
            result = await self._collection.update_one(
                {"_id": entity.id, "version": expected_version},
                {"$set": document},
                upsert=(expected_version == 1),
            )

            if result.matched_count == 0 and result.upserted_id is None:
                entity.version = expected_version
                raise ConcurrencyError(
                    f"Version mismatch for {entity.__class__.__name__} (id: {entity.id})"
                )
        except DuplicateKeyError:
            entity.version = expected_version
            raise ConcurrencyError(
                f"Version mismatch for {entity.__class__.__name__} (id: {entity.id})"
            )

    async def save_and_publish(self, entity: T) -> None:
        await self.save(entity)

        async def publish_messages():
            for message in entity.outbox:
                await self._message_broker.publish_message(
                    message.model_dump_json(),
                    stream_name=f"{entity.__class__.__name__.lower()}-events",
                )
                message_doc = message.model_dump()
                message_doc.pop("_id", None)
                await self._messages_collection.update_one(
                    {"_id": message.id},
                    {"$set": message_doc},
                    upsert=True,
                )
            entity.clear_outbox()

            for processed_message in entity.processed_messages:
                processed_message_doc = processed_message.model_dump()
                processed_message_doc.pop("_id", None)
                await self._processed_messages_collection.update_one(
                    {"_id": processed_message.id},
                    {"$set": processed_message_doc},
                    upsert=True,
                )
            entity.clear_processed_messages()

            await self.save(entity)

        await publish_messages()

    async def find_by_id(self, entity_id: UUID) -> T | None:
        document = await self._collection.find_one(
            {"_id": entity_id, "is_deleted": False}
        )
        if document is None:
            return None
        return self._entity_class.model_validate(document)
