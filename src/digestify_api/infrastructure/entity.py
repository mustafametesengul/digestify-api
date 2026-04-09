from datetime import datetime, UTC

from pydantic import BaseModel, Field

from uuid import UUID, uuid7


class Message(BaseModel):
    id: UUID = Field(default_factory=uuid7, alias="_id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    entity_id: UUID = Field(default_factory=uuid7)
    entity_version: int = 0


class ProcessedMessage(BaseModel):
    id: UUID = Field(default_factory=uuid7, alias="_id")
    message_id: UUID
    entity_id: UUID


class Entity(BaseModel):
    id: UUID = Field(default_factory=uuid7, alias="_id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    is_deleted: bool = False
    version: int = 0
    outbox: list[Message] = Field(default_factory=list)
    processed_messages: list[ProcessedMessage] = Field(default_factory=list)

    def mark_message_as_processed(self, message: Message) -> None:
        processed_message = ProcessedMessage(message_id=message.id, entity_id=self.id)
        self.processed_messages.append(processed_message)

    def clear_processed_messages(self) -> None:
        self.processed_messages.clear()

    def add_to_outbox(self, message: Message) -> None:
        message.entity_id = self.id
        message.entity_version = self.version + 1
        self.outbox.append(message)

    def clear_outbox(self) -> None:
        self.outbox.clear()

    def delete(self) -> None:
        self.is_deleted = True
