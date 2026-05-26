from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


def create_engine(database_url: str = settings.database_url) -> AsyncEngine:
    return create_async_engine(database_url, pool_pre_ping=True)


engine = create_engine()
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


def get_db_engine() -> AsyncEngine:
    return engine


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def close_db_engine() -> None:
    await engine.dispose()
