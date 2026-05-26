from app.models import KnowledgeBase, KnowledgeChunk, KnowledgeDocument, KnowledgeVector


def test_knowledge_base_model_maps_to_existing_table_name() -> None:
    assert KnowledgeBase.__tablename__ == "t_knowledge_base"
    assert {"id", "name", "status", "created_by"}.issubset(KnowledgeBase.__table__.columns.keys())


def test_knowledge_document_model_maps_kb_foreign_key() -> None:
    foreign_keys = KnowledgeDocument.__table__.columns["kb_id"].foreign_keys

    assert KnowledgeDocument.__tablename__ == "t_knowledge_document"
    assert any(key.target_fullname == "t_knowledge_base.id" for key in foreign_keys)


def test_knowledge_chunk_model_maps_document_foreign_key() -> None:
    foreign_keys = KnowledgeChunk.__table__.columns["doc_id"].foreign_keys

    assert KnowledgeChunk.__tablename__ == "t_knowledge_chunk"
    assert any(key.target_fullname == "t_knowledge_document.id" for key in foreign_keys)


def test_knowledge_vector_model_maps_chunk_foreign_key() -> None:
    foreign_keys = KnowledgeVector.__table__.columns["chunk_id"].foreign_keys

    assert KnowledgeVector.__tablename__ == "t_knowledge_vector"
    assert any(key.target_fullname == "t_knowledge_chunk.id" for key in foreign_keys)
