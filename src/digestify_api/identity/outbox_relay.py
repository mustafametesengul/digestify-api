import asyncio

from pymongo.asynchronous.collection import AsyncCollection

from digestify_api.infrastructure.message_broker import MessageBroker


class OutboxRelay:
    def __init__(
        self,
        entity_collection: AsyncCollection,
        messages_collection: AsyncCollection,
        message_broker: MessageBroker,
        batch_size: int = 10,
        poll_interval: float = 60.0,
    ) -> None:
        self._entity_collection = entity_collection
        self._messages_collection = messages_collection
        self._message_broker = message_broker
        self._batch_size = batch_size
        self._poll_interval = poll_interval

    async def change_stream(self) -> None:
        async with await self._entity_collection.watch() as stream:
            async for change in stream:
                if change["operationType"] in ("insert", "update"):
                    document = change["fullDocument"]
                    outbox = document.get("outbox", [])
                    if not outbox:
                        continue

                    # Publish events to message broker and store in messages collection
                    for event in outbox:
                        await self._messages_collection.update_one(
                            {"id": event.id},
                            {"$setOnInsert": event.model_dump()},
                            upsert=True,
                        )
                        await self._message_broker.publish_message(str(event), "events")

                    # Clear the outbox
                    await self._entity_collection.update_one(
                        {"_id": document["_id"]}, {"$set": {"outbox": []}}
                    )

    async def sweeper(self) -> None:
        while True:
            # Find documents with non-empty outbox
            cursor = self._entity_collection.find({"outbox": {"$ne": []}}).limit(
                self._batch_size
            )
            async for document in cursor:
                outbox = document.get("outbox", [])
                if not outbox:
                    continue

                # Publish events to message broker and store in messages collection
                for event in outbox:
                    await self._messages_collection.update_one(
                        {"id": event.id},
                        {"$setOnInsert": event.model_dump()},
                        upsert=True,
                    )
                    await self._message_broker.publish_message(str(event), "events")

                # Clear the outbox
                await self._entity_collection.update_one(
                    {"_id": document["_id"]}, {"$set": {"outbox": []}}
                )

            await asyncio.sleep(self._poll_interval)
