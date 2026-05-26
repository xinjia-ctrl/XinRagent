from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

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

    assert engine.url.drivername == "postgresql+asyncpg"
    assert engine.url.database == "ragent"


def test_session_factory_creates_async_session() -> None:
    session = AsyncSessionLocal()

    try:
        assert isinstance(session, AsyncSession)
        assert session.sync_session.autoflush is False
        assert session.sync_session.expire_on_commit is False
    finally:
        session.sync_session.close()
