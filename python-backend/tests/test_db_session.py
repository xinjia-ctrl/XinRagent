from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.config import settings
from app.db.session import AsyncSessionLocal, create_engine, get_db_engine


def test_create_engine_uses_asyncpg_driver() -> None:
    engine = create_engine("postgresql+asyncpg://postgres:postgres@localhost:5432/ragent")

    try:
        assert isinstance(engine, AsyncEngine)
        assert engine.url.drivername == "postgresql+asyncpg"
    finally:
        engine.sync_engine.dispose()


def test_global_engine_uses_configured_database_url() -> None:
    engine = get_db_engine()
    configured_engine = create_engine(settings.database_url)

    try:
        assert engine.url.drivername == configured_engine.url.drivername
        assert engine.url.database == configured_engine.url.database
    finally:
        configured_engine.sync_engine.dispose()


def test_session_factory_creates_async_session() -> None:
    session = AsyncSessionLocal()

    try:
        assert isinstance(session, AsyncSession)
        assert session.sync_session.autoflush is False
        assert session.sync_session.expire_on_commit is False
    finally:
        session.sync_session.close()
