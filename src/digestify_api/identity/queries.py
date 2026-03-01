from datetime import datetime
from uuid import UUID

from asyncpg import Connection
from pydantic import BaseModel


class User(BaseModel):
    id: UUID
    username: str | None
    password_hash: str | None
    created_at: datetime
    updated_at: datetime | None
    version: int
    is_deleted: bool


async def create_tables(connection: Connection) -> None:
    await connection.execute(
        """
        CREATE TABLE users (
            id UUID PRIMARY KEY,
            username TEXT UNIQUE,
            password_hash TEXT,
            discarded BOOLEAN NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE,
            version INTEGER NOT NULL
        );

        CREATE INDEX ix_users_username ON users (username);
        CREATE INDEX ix_users_discarded ON users (discarded);
        """
    )


async def create_user(conn: Connection, user: User) -> None:
    await conn.execute(
        """
        INSERT INTO users
        (id, username, password_hash, discarded, created_at, updated_at, version)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        """,
        user.id,
        user.username,
        user.password_hash,
        user.is_deleted,
        user.created_at,
        user.updated_at,
        user.version,
    )


async def update_user(conn: Connection, user: User) -> None:
    await conn.execute(
        """
        UPDATE users
        SET discarded = $2,
            updated_at = $3,
            version = $4
            WHERE id = $1
        """,
        user.id,
        user.is_deleted,
        user.updated_at,
        user.version,
    )


async def get_user(conn: Connection, user_id: UUID, lock: bool = False) -> User | None:
    query = "SELECT * FROM users WHERE id = $1"
    if lock:
        query += " FOR UPDATE"
    row = await conn.fetchrow(query, user_id)
    if row is None:
        return None
    return User.model_validate(dict(row))


async def get_user_by_username(conn: Connection, username: str) -> User | None:
    row = await conn.fetchrow("SELECT * FROM users WHERE username = $1", username)
    if row is None:
        return None
    return User.model_validate(dict(row))
