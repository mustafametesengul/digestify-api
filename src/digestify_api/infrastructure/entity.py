from datetime import datetime, UTC, timedelta

from pydantic import BaseModel, Field

from uuid import UUID, uuid7


class Message(BaseModel):
    id: UUID = Field(default_factory=uuid7, alias="_id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    entity_id: UUID = Field(default_factory=uuid7)
    entity_version: int = 0


class Entity(BaseModel):
    id: UUID = Field(default_factory=uuid7, alias="_id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    is_discarded: bool = False
    version: int = 0
    outbox: list[Message] = Field(default_factory=list)
    published_messages: list[Message] = Field(default_factory=list)

    def discard(self) -> None:
        self.is_discarded = True

    def check_outbox_limit(self) -> None:
        if len(self.outbox) >= 100:
            raise Exception("Outbox limit exceeded")

    def check_published_messages_limit(self) -> None:
        if len(self.published_messages) >= 1000:
            raise Exception("Published messages limit exceeded")

    def check_if_message_processed(self, message: Message) -> None:
        cutoff_time = datetime.now(UTC) - timedelta(days=7)
        if message.created_at < cutoff_time:
            raise Exception("Cannot check if message is processed: message is too old")
        already_processed = any(
            processed_message.message_id == message.id
            for processed_message in self.processed_messages
        )
        if already_processed:
            raise Exception("Message has already been processed")

    def add_to_outbox(self, message: Message) -> None:
        message.entity_id = self.id
        message.entity_version = self.version + 1
        self.outbox.append(message)
        self.check_outbox_limit()

    def move_outbox_to_published(self) -> None:
        self.published_messages.extend(self.outbox)
        self.check_published_messages_limit()
        self.outbox.clear()

    def move_published_to_outbox(self) -> None:
        self.outbox.extend(self.published_messages)
        self.published_messages.clear()

    def delete_old_messages(self) -> None:
        cutoff_time = datetime.now(UTC) - timedelta(
            days=PUBLISHED_MESSAGE_RETENTION_DAYS
        )
        self.published_messages = [
            message
            for message in self.published_messages
            if message.created_at >= cutoff_time
        ]
