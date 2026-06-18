from pathlib import Path
import importlib.util

from app.db.base import Base
import app.models  # noqa: F401


REPO_ROOT = Path(__file__).resolve().parents[2]
INITIAL_MIGRATION = REPO_ROOT / "python-backend" / "alembic" / "versions" / "0001_initial_schema.py"


def _load_initial_migration():
    spec = importlib.util.spec_from_file_location("xinragent_initial_schema", INITIAL_MIGRATION)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_alembic_script_directory_exists() -> None:
    assert (REPO_ROOT / "python-backend" / "alembic" / "env.py").is_file()
    assert INITIAL_MIGRATION.is_file()


def test_postgres_schema_sql_is_tracked_database_source() -> None:
    schema_sql = REPO_ROOT / "resources" / "database" / "schema_pg.sql"

    assert schema_sql.is_file()
    assert "CREATE TABLE t_rag_trace_run" in schema_sql.read_text(encoding="utf-8")


def test_orm_metadata_covers_schema_core_tables() -> None:
    assert {
        "t_user",
        "t_conversation",
        "t_message",
        "t_knowledge_base",
        "t_knowledge_document",
        "t_knowledge_chunk",
        "t_knowledge_vector",
        "t_intent_node",
        "t_query_term_mapping",
        "t_sample_question",
        "t_rag_trace_run",
        "t_rag_trace_node",
        "t_ingestion_pipeline",
        "t_ingestion_pipeline_node",
        "t_ingestion_task",
        "t_ingestion_task_node",
    }.issubset(Base.metadata.tables.keys())


def test_initial_migration_splits_sql_without_breaking_quoted_semicolons() -> None:
    migration = _load_initial_migration()

    statements = list(migration._iter_sql_statements("SELECT 'a;b';\nSELECT 2;"))

    assert statements == ["SELECT 'a;b';", "SELECT 2;"]
