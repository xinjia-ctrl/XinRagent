from collections.abc import AsyncIterator

import pytest

from app.infra_ai.chat import ChatChunk, ChatRequest
from app.rag.pipeline import StreamChatContext, StreamChatPipeline
from app.rag.prompt import ContextFormatter, PromptService
from app.rag.retrieve import RetrievedChunk


class FakeRetrievalEngine:
    async def retrieve(self, **_: object) -> list[RetrievedChunk]:
        return [
            RetrievedChunk(
                id="chunk-1",
                content="Ragent 支持基于 pgvector 的知识库检索。",
                score=0.92,
                metadata={"docName": "Ragent 文档"},
            ),
        ]


class CapturingLLMService:
    def __init__(self) -> None:
        self.request: ChatRequest | None = None

    async def stream(self, request: ChatRequest) -> AsyncIterator[ChatChunk]:
        self.request = request
        yield ChatChunk(delta="已基于知识库回答")


def test_context_formatter_formats_retrieved_chunks() -> None:
    formatter = ContextFormatter()
    context = formatter.format_chunks(
        [
            RetrievedChunk(
                id="chunk-1",
                content="知识片段",
                score=0.87654,
                metadata={"docName": "文档 A"},
            ),
        ],
    )

    assert "来源: 文档 A" in context
    assert "相关度: 0.8765" in context
    assert "内容: 知识片段" in context


def test_prompt_service_includes_retrieval_context() -> None:
    service = PromptService()
    messages = service.build_messages(
        "Ragent 支持什么检索？",
        [RetrievedChunk(id="chunk-1", content="支持 pgvector", score=0.9)],
    )

    assert messages[0].role == "system"
    assert "知识库上下文" in messages[0].content
    assert "支持 pgvector" in messages[0].content
    assert messages[1].content == "Ragent 支持什么检索？"


@pytest.mark.asyncio
async def test_stream_chat_pipeline_uses_retrieval_context_in_prompt() -> None:
    llm_service = CapturingLLMService()
    pipeline = StreamChatPipeline(
        llm_service=llm_service,
        retrieval_engine=FakeRetrievalEngine(),
    )
    context = StreamChatContext(
        question="Ragent 支持什么检索？",
        conversation_id="conv-1",
        task_id="task-1",
        user_id="user-1",
    )

    deltas = [delta async for delta in pipeline.execute(context)]

    assert deltas == ["已基于知识库回答"]
    assert llm_service.request is not None
    system_message = llm_service.request.messages[0]
    assert "Ragent 支持基于 pgvector 的知识库检索。" in system_message.content
    assert "Ragent 文档" in system_message.content
