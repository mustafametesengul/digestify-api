from datetime import datetime
from uuid import UUID

from asyncpg import Connection
from pydantic import BaseModel


class Message(BaseModel):
    id: UUID
    channel: str
    type: str
    payload: str
    created_at: datetime
    scheduled_at: datetime


async def create_message(conn: Connection, message: Message) -> None:
    await conn.execute(
        """
        INSERT INTO messages
        (id, channel, type, payload, scheduled_at, created_at)
        VALUES ($1, $2, $3, $4, $5, $6)
        """,
        message.id,
        message.channel,
        message.type,
        message.payload,
        message.scheduled_at,
        message.created_at,
    )
