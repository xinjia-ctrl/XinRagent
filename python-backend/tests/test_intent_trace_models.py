from app.models import IntentNode, RagTraceNode, RagTraceRun


def test_intent_node_model_maps_parent_foreign_key() -> None:
    foreign_keys = IntentNode.__table__.columns["parent_id"].foreign_keys

    assert IntentNode.__tablename__ == "t_intent_node"
    assert any(key.target_fullname == "t_intent_node.id" for key in foreign_keys)


def test_trace_run_model_maps_core_columns() -> None:
    assert RagTraceRun.__tablename__ == "t_rag_trace_run"
    assert {"id", "conversation_id", "question", "status", "latency_ms"}.issubset(
        RagTraceRun.__table__.columns.keys(),
    )


def test_trace_node_model_maps_run_foreign_key() -> None:
    foreign_keys = RagTraceNode.__table__.columns["run_id"].foreign_keys

    assert RagTraceNode.__tablename__ == "t_rag_trace_node"
    assert any(key.target_fullname == "t_rag_trace_run.id" for key in foreign_keys)
