import os
from uuid import uuid4

import pytest

from app.infra_ai.embedding import EmbeddingRequest, EmbeddingResponse
from app.rag.retrieve import MilvusVectorStoreService, VectorCollectionSpec, VectorIndexChunk


class FixedEmbeddingService:
    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        assert request.texts
        return EmbeddingResponse(vectors=[[0.11, 0.22, 0.33]], model=request.model)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_milvus_collection_lifecycle_indexes_searches_deletes_and_rebuilds() -> None:
    if os.getenv("MILVUS_INTEGRATION_ENABLED", "").lower() not in {"1", "true", "yes"}:
        pytest.skip("设置 MILVUS_INTEGRATION_ENABLED=true 后才运行真实 Milvus 集成测试")

    pytest.importorskip("pymilvus")
    collection_name = f"codex_milvus_{uuid4().hex[:12]}"
    service = MilvusVectorStoreService(
        embedding_service=FixedEmbeddingService(),
        collection_name=collection_name,
        dimension=3,
    )

    try:
        await service.rebuild_collection(VectorCollectionSpec(name=collection_name, dimension=3))
        await service.index_chunks(
            collection_name,
            [
                VectorIndexChunk(
                    id="chunk-1",
                    content="Ragent Python Milvus 真实入库验证",
                    vector=[0.11, 0.22, 0.33],
                    metadata={"kbId": "kb-real", "docId": "doc-real"},
                ),
            ],
        )

        chunks = await service.search(
            "Milvus 入库验证",
            top_k=1,
            kb_id="kb-real",
            collection_name=collection_name,
        )
        assert chunks
        assert chunks[0].id == "chunk-1"

        await service.delete_chunks(collection_name, ["chunk-1"])
        chunks_after_delete = await service.search(
            "Milvus 入库验证",
            top_k=1,
            kb_id="kb-real",
            collection_name=collection_name,
        )
        assert all(chunk.id != "chunk-1" for chunk in chunks_after_delete)

        await service.rebuild_collection(VectorCollectionSpec(name=collection_name, dimension=3))
        await service.index_chunks(
            collection_name,
            [
                VectorIndexChunk(
                    id="chunk-2",
                    content="Ragent Python Milvus 重建索引验证",
                    vector=[0.11, 0.22, 0.33],
                    metadata={"kbId": "kb-real", "docId": "doc-rebuild"},
                ),
            ],
        )
        rebuilt_chunks = await service.search(
            "Milvus 重建索引验证",
            top_k=1,
            kb_id="kb-real",
            collection_name=collection_name,
        )
        assert rebuilt_chunks[0].id == "chunk-2"
    finally:
        await service.drop_collection(collection_name)
