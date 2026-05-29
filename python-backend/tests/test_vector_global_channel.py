from unittest.mock import AsyncMock

import pytest

from app.rag.retrieve import RetrievedChunk
from app.rag.retrieve.channels import SearchContext, VectorGlobalSearchChannel
from app.rag.retrieve.multi_channel_retrieval_engine import MultiChannelRetrievalEngine


@pytest.mark.asyncio
async def test_vector_global_channel_delegates_to_vector_store() -> None:
    vector_store = AsyncMock()
    vector_store.search.return_value = [RetrievedChunk(id="1", content="A", score=0.8)]
    channel = VectorGlobalSearchChannel(vector_store)

    chunks = await channel.search(SearchContext(query="问题", top_k=2))

    assert chunks[0].content == "A"
    vector_store.search.assert_awaited_once_with("问题", top_k=2)


@pytest.mark.asyncio
async def test_multi_channel_engine_sorts_and_deduplicates_chunks() -> None:
    first = AsyncMock()
    first.search.return_value = [
        RetrievedChunk(id="low", content="低分", score=0.3),
        RetrievedChunk(id="same", content="重复低分", score=0.4),
    ]
    second = AsyncMock()
    second.search.return_value = [
        RetrievedChunk(id="same", content="重复高分", score=0.9),
        RetrievedChunk(id="top", content="高分", score=0.95),
    ]
    engine = MultiChannelRetrievalEngine([first, second])

    chunks = await engine.retrieve_knowledge_channels(SearchContext(query="问题", top_k=2))

    assert [chunk.id for chunk in chunks] == ["top", "same"]
    assert chunks[1].content == "重复高分"
