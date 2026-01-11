from typing import AsyncIterator

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.ext.asyncio.engine import AsyncEngine, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession


class DBSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_host: str = Field(default=...)
    postgres_port: int = Field(default=...)
    postgres_user: str = Field(default=...)
    postgres_password: str = Field(default=...)
    postgres_db: str = Field(default=...)


engine: AsyncEngine | None = None


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


def init_engine(settings: DBSettings | None = None) -> None:
    global engine
    if engine is not None:
        raise ValueError("Engine has already been initialized.")
    if settings is None:
        settings = DBSettings()
    url = create_database_url(
        driver="postgresql+asyncpg",
        user=settings.postgres_user,
        password=settings.postgres_password,
        host=settings.postgres_host,
        port=settings.postgres_port,
        db=settings.postgres_db,
    )
    engine = create_async_engine(url)


def get_engine() -> AsyncEngine:
    global engine
    if engine is None:
        raise ValueError("Engine has not been initialized.")
    return engine


async def dispose_engine() -> None:
    global engine
    engine = get_engine()
    await engine.dispose()
    engine = None


async def get_session() -> AsyncIterator[AsyncSession]:
    engine = get_engine()
    async with AsyncSession(engine) as session:
        yield session
        await session.commit()
