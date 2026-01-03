from typing import AsyncIterator

from sqlalchemy.ext.asyncio.engine import AsyncEngine, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from digestify_api.settings import get_settings

_engine: AsyncEngine | None = None


def create_database_url(
    driver: str,
    user: str,
    password: str,
    host: str,
    port: int,
    db: str,
) -> str:
    url = f"{driver}://{user}:{password}@{host}:{port}/{db}"
    return url


def init_engine() -> None:
    global _engine
    if _engine is not None:
        raise ValueError("Engine has already been initialized.")
    settings = get_settings()
    url = create_database_url(
        driver="postgresql+asyncpg",
        user=settings.postgres_user,
        password=settings.postgres_password,
        host=settings.postgres_host,
        port=settings.postgres_port,
        db=settings.postgres_db,
    )
    _engine = create_async_engine(url)


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        raise ValueError("Engine has not been initialized.")
    return _engine


async def dispose_engine() -> None:
    global _engine
    engine = get_engine()
    await engine.dispose()
    _engine = None


async def get_session() -> AsyncIterator[AsyncSession]:
    engine = get_engine()
    async with AsyncSession(engine) as session:
        yield session
