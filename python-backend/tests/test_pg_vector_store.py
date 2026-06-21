from unittest.mock import AsyncMock

import pytest

from app.infra_ai.embedding import EmbeddingResponse
from app.rag.retrieve import (
    MilvusVectorStoreService,
    PgVectorStoreService,
    VectorCollectionSpec,
    VectorIndexChunk,
)


class FakeMappingResult:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows

    def mappings(self) -> "FakeMappingResult":
        return self

    def all(self) -> list[dict]:
        return self.rows


@pytest.mark.asyncio
async def test_pg_vector_store_search_embeds_query_and_maps_rows() -> None:
    session = AsyncMock()
    session.execute.return_value = FakeMappingResult(
        [
            {
                "id": "chunk-1",
                "content": "RAG 内容",
                "metadata": {"docId": "doc-1"},
                "score": 0.91,
            },
        ],
    )
    embedding_service = AsyncMock()
    embedding_service.embed.return_value = EmbeddingResponse(vectors=[[0.1, 0.2]], model="embed")
    service = PgVectorStoreService(session, embedding_service)

    chunks = await service.search("什么是 RAG", top_k=3)

    assert len(chunks) == 1
    assert chunks[0].id == "chunk-1"
    assert chunks[0].content == "RAG 内容"
    assert chunks[0].score == 0.91
    assert chunks[0].metadata == {"docId": "doc-1"}
    session.execute.assert_awaited_once()
    params = session.execute.await_args.args[1]
    assert params["query_vector"] == "[0.1,0.2]"
    assert params["top_k"] == 3


@pytest.mark.asyncio
async def test_pg_vector_store_returns_empty_when_embedding_is_empty() -> None:
    session = AsyncMock()
    embedding_service = AsyncMock()
    embedding_service.embed.return_value = EmbeddingResponse(vectors=[], model="embed")
    service = PgVectorStoreService(session, embedding_service)

    chunks = await service.search("空向量")

    assert chunks == []
    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_pg_vector_store_indexes_chunks_with_collection_metadata() -> None:
    session = AsyncMock()
    embedding_service = AsyncMock()
    service = PgVectorStoreService(session, embedding_service)

    await service.index_chunks(
        "kb_docs",
        [
            VectorIndexChunk(
                id="chunk-1",
                content="内容",
                vector=[0.1, 0.2],
                metadata={"kbId": "kb-1"},
            ),
        ],
    )

    params = session.execute.await_args.args[1]
    assert params["id"] == "chunk-1"
    assert params["embedding"] == "[0.1,0.2]"
    assert '"collectionName": "kb_docs"' in params["metadata"]


class FakeMilvusClient:
    def __init__(self) -> None:
        self.collections: set[str] = set()
        self.created: list[dict] = []
        self.upserts: list[dict] = []
        self.searches: list[dict] = []
        self.deletes: list[dict] = []
        self.dropped: list[str] = []
        self.flushed: list[str] = []

    def has_collection(self, collection_name: str) -> bool:
        return collection_name in self.collections

    def create_collection(self, **kwargs) -> None:
        self.created.append(kwargs)
        self.collections.add(kwargs["collection_name"])

    def upsert(self, **kwargs) -> None:
        self.upserts.append(kwargs)

    def delete(self, **kwargs) -> None:
        self.deletes.append(kwargs)

    def drop_collection(self, collection_name: str) -> None:
        self.dropped.append(collection_name)
        self.collections.discard(collection_name)

    def flush(self, **kwargs) -> None:
        self.flushed.append(kwargs["collection_name"])

    def search(self, **kwargs):
        self.searches.append(kwargs)
        return [
            [
                {
                    "id": "chunk-1",
                    "score": 0.88,
                    "entity": {
                        "content": "Milvus 内容",
                        "metadata": {"kbId": "kb-1"},
                    },
                },
            ],
        ]


@pytest.mark.asyncio
async def test_milvus_vector_store_manages_collection_and_indexes_chunks() -> None:
    client = FakeMilvusClient()
    service = MilvusVectorStoreService(client=client)

    await service.ensure_collection(VectorCollectionSpec(name="kb_docs", dimension=2))
    await service.index_chunks(
        "kb_docs",
        [
            VectorIndexChunk(
                id="chunk-1",
                content="Milvus 内容",
                vector=[0.1, 0.2],
                metadata={"kbId": "kb-1"},
            ),
        ],
    )

    assert client.created[0]["collection_name"] == "ragent_kb_docs"
    assert client.created[0]["dimension"] == 2
    assert client.upserts[0]["collection_name"] == "ragent_kb_docs"
    assert client.upserts[0]["data"][0]["metadata"]["collectionName"] == "kb_docs"
    assert client.flushed == ["ragent_kb_docs"]


@pytest.mark.asyncio
async def test_milvus_vector_store_searches_selected_collection() -> None:
    client = FakeMilvusClient()
    client.collections.add("ragent_kb_docs")
    embedding_service = AsyncMock()
    embedding_service.embed.return_value = EmbeddingResponse(vectors=[[0.1, 0.2]], model="embed")
    service = MilvusVectorStoreService(embedding_service=embedding_service, client=client)

    chunks = await service.search("什么是 RAG", top_k=2, kb_id="kb-1", collection_name="kb_docs")

    assert chunks[0].id == "chunk-1"
    assert chunks[0].content == "Milvus 内容"
    assert chunks[0].score == pytest.approx(0.88)
    assert client.searches[0]["collection_name"] == "ragent_kb_docs"
    assert client.searches[0]["filter"] == 'metadata["kbId"] == "kb-1"'


@pytest.mark.asyncio
async def test_milvus_vector_store_deletes_chunks_and_rebuilds_collection() -> None:
    client = FakeMilvusClient()
    client.collections.add("ragent_kb_docs")
    service = MilvusVectorStoreService(client=client)

    await service.delete_chunks("kb_docs", ["chunk-1", "chunk-2"])
    await service.rebuild_collection(VectorCollectionSpec(name="kb_docs", dimension=2))

    assert client.deletes[0]["collection_name"] == "ragent_kb_docs"
    assert client.deletes[0]["ids"] == ["chunk-1", "chunk-2"]
    assert client.dropped == ["ragent_kb_docs"]
    assert client.created[-1]["collection_name"] == "ragent_kb_docs"
