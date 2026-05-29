from unittest.mock import AsyncMock

import pytest

from app.infra_ai.embedding import EmbeddingResponse
from app.rag.retrieve import PgVectorStoreService


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
