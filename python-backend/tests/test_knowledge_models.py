from app.models import KnowledgeBase, KnowledgeChunk, KnowledgeDocument, KnowledgeVector


def test_knowledge_base_model_maps_to_existing_table_name() -> None:
    assert KnowledgeBase.__tablename__ == "t_knowledge_base"
    assert {
        "id",
        "name",
        "embedding_model",
        "collection_name",
        "created_by",
        "updated_by",
        "deleted",
    }.issubset(KnowledgeBase.__table__.columns.keys())


def test_knowledge_document_model_maps_postgres_schema_columns() -> None:
    assert KnowledgeDocument.__tablename__ == "t_knowledge_document"
    assert {
        "id",
        "kb_id",
        "doc_name",
        "enabled",
        "chunk_count",
        "file_url",
        "file_type",
        "process_mode",
        "source_location",
        "chunk_config",
        "pipeline_id",
        "created_by",
        "updated_by",
        "deleted",
    }.issubset(KnowledgeDocument.__table__.columns.keys())


def test_knowledge_chunk_model_maps_postgres_schema_columns() -> None:
    assert KnowledgeChunk.__tablename__ == "t_knowledge_chunk"
    assert {
        "id",
        "kb_id",
        "doc_id",
        "chunk_index",
        "content",
        "content_hash",
        "char_count",
        "token_count",
        "enabled",
        "created_by",
        "updated_by",
        "deleted",
    }.issubset(KnowledgeChunk.__table__.columns.keys())


def test_knowledge_vector_model_maps_pgvector_schema_columns() -> None:
    assert KnowledgeVector.__tablename__ == "t_knowledge_vector"
    assert {"id", "content", "metadata", "embedding"}.issubset(KnowledgeVector.__table__.columns.keys())
