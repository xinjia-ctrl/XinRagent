from app.models import IntentNode, RagTraceNode, RagTraceRun


def test_intent_node_model_maps_postgres_schema_columns() -> None:
    assert IntentNode.__tablename__ == "t_intent_node"
    assert {
        "id",
        "kb_id",
        "intent_code",
        "level",
        "parent_code",
        "collection_name",
        "prompt_template",
        "create_by",
        "update_by",
        "deleted",
    }.issubset(IntentNode.__table__.columns.keys())


def test_trace_run_model_maps_core_columns() -> None:
    assert RagTraceRun.__tablename__ == "t_rag_trace_run"
    assert {
        "id",
        "trace_id",
        "trace_name",
        "entry_method",
        "conversation_id",
        "task_id",
        "user_id",
        "status",
        "error_message",
        "start_time",
        "end_time",
        "duration_ms",
        "extra_data",
        "deleted",
    }.issubset(
        RagTraceRun.__table__.columns.keys(),
    )


def test_trace_node_model_maps_postgres_schema_columns() -> None:
    assert RagTraceNode.__tablename__ == "t_rag_trace_node"
    assert {
        "id",
        "trace_id",
        "node_id",
        "parent_node_id",
        "depth",
        "node_type",
        "node_name",
        "class_name",
        "method_name",
        "status",
        "error_message",
        "start_time",
        "end_time",
        "duration_ms",
        "extra_data",
        "deleted",
    }.issubset(RagTraceNode.__table__.columns.keys())
