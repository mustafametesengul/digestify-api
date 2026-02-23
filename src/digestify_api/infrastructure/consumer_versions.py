from asyncpg import Connection
from pydantic import BaseModel


class ConsumerVersion(BaseModel):
    handler_name: str
    producer: str
    last_version: int


async def create_consumer_versions_table(connection: Connection) -> None:
    await connection.execute(
        """
        CREATE TABLE consumer_versions (
            handler_name TEXT NOT NULL,
            producer TEXT NOT NULL,
            last_version INT NOT NULL,
            PRIMARY KEY (handler_name, producer)
        );
        """
    )


async def get_consumer_version(
    conn: Connection, handler_name: str, producer: str
) -> int:
    row = await conn.fetchrow(
        """
        SELECT last_version
        FROM consumer_versions
        WHERE handler_name = $1 AND producer = $2
        """,
        handler_name,
        producer,
    )
    if row:
        return row["last_version"]
    return 0


async def update_consumer_version(
    conn: Connection, handler_name: str, producer: str, version: int
) -> None:
    await conn.execute(
        """
        INSERT INTO consumer_versions (handler_name, producer, last_version)
        VALUES ($1, $2, $3)
        ON CONFLICT (handler_name, producer)
        DO UPDATE SET last_version = EXCLUDED.last_version
        WHERE consumer_versions.last_version < EXCLUDED.last_version
        """,
        handler_name,
        producer,
        version,
    )


migrations = [create_consumer_versions_table]
