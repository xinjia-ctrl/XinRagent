"""initial PostgreSQL schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-06-18
"""

from pathlib import Path

from alembic import context, op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def _schema_path() -> Path:
    return Path(__file__).resolve().parents[3] / "resources" / "database" / "schema_pg.sql"


def _load_schema_sql() -> str:
    path = _schema_path()
    if not path.exists():
        raise RuntimeError(f"数据库初始化脚本不存在: {path}")
    return path.read_text(encoding="utf-8")


def _iter_sql_statements(sql: str):
    statement: list[str] = []
    in_single_quote = False
    index = 0
    while index < len(sql):
        char = sql[index]
        statement.append(char)
        if char == "'":
            next_char = sql[index + 1] if index + 1 < len(sql) else ""
            if in_single_quote and next_char == "'":
                statement.append(next_char)
                index += 2
                continue
            in_single_quote = not in_single_quote
        elif char == ";" and not in_single_quote:
            current = "".join(statement).strip()
            if current:
                yield current
            statement = []
        index += 1

    tail = "".join(statement).strip()
    if tail:
        yield tail


def upgrade() -> None:
    schema_sql = _load_schema_sql()
    if context.is_offline_mode():
        op.execute(schema_sql)
        return
    bind = op.get_bind()
    for statement in _iter_sql_statements(schema_sql):
        bind.exec_driver_sql(statement)


def downgrade() -> None:
    downgrade_sql = """
        DROP TABLE IF EXISTS t_knowledge_vector CASCADE;
        DROP TABLE IF EXISTS t_ingestion_task_node CASCADE;
        DROP TABLE IF EXISTS t_ingestion_task CASCADE;
        DROP TABLE IF EXISTS t_ingestion_pipeline_node CASCADE;
        DROP TABLE IF EXISTS t_ingestion_pipeline CASCADE;
        DROP TABLE IF EXISTS t_rag_trace_node CASCADE;
        DROP TABLE IF EXISTS t_rag_trace_run CASCADE;
        DROP TABLE IF EXISTS t_query_term_mapping CASCADE;
        DROP TABLE IF EXISTS t_intent_node CASCADE;
        DROP TABLE IF EXISTS t_knowledge_document_schedule_exec CASCADE;
        DROP TABLE IF EXISTS t_knowledge_document_schedule CASCADE;
        DROP TABLE IF EXISTS t_knowledge_document_chunk_log CASCADE;
        DROP TABLE IF EXISTS t_knowledge_chunk CASCADE;
        DROP TABLE IF EXISTS t_knowledge_document CASCADE;
        DROP TABLE IF EXISTS t_knowledge_base CASCADE;
        DROP TABLE IF EXISTS t_sample_question CASCADE;
        DROP TABLE IF EXISTS t_message_feedback CASCADE;
        DROP TABLE IF EXISTS t_message CASCADE;
        DROP TABLE IF EXISTS t_conversation_summary CASCADE;
        DROP TABLE IF EXISTS t_conversation CASCADE;
        DROP TABLE IF EXISTS t_user CASCADE;
        DROP EXTENSION IF EXISTS vector;
        """
    if context.is_offline_mode():
        op.execute(downgrade_sql)
        return
    bind = op.get_bind()
    for statement in _iter_sql_statements(downgrade_sql):
        bind.exec_driver_sql(statement)
