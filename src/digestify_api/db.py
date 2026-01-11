from typing import AsyncIterator

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.ext.asyncio.engine import AsyncEngine, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession


class DBSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_prefix="POSTGRES_",
    )

    host: str = Field(default=...)
    port: int = Field(default=...)
    user: str = Field(default=...)
    password: str = Field(default=...)
    db: str = Field(default=...)


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


def create_engine(settings: DBSettings | None = None) -> None:
    global _engine
    if _engine is not None:
        raise ValueError("Engine has already been initialized.")
    settings = settings or DBSettings()
    url = create_database_url(
        driver="postgresql+asyncpg",
        user=settings.user,
        password=settings.password,
        host=settings.host,
        port=settings.port,
        db=settings.db,
    )
    _engine = create_async_engine(url)


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        raise ValueError("Engine has not been initialized.")
    return _engine


async def dispose_engine() -> None:
    global _engine
    _engine = get_engine()
    await _engine.dispose()
    _engine = None


async def get_session() -> AsyncIterator[AsyncSession]:
    engine = get_engine()
    async with AsyncSession(engine) as session:
        yield session
        await session.commit()
