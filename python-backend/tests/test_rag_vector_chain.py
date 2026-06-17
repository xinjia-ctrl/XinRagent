from collections.abc import AsyncIterator
from dataclasses import dataclass

import pytest

from app.infra_ai.chat import ChatChunk, ChatMessage, ChatRequest
from app.infra_ai.rerank import RerankDocument, RerankResponse
from app.mcp import MCPResponse, MCPService
from app.rag.intent import IntentMatch, IntentResolution
from app.rag.pipeline import StreamChatContext, StreamChatPipeline
from app.rag.prompt import ContextFormatter, PromptService
from app.rag.retrieve import RetrievedChunk
from app.rag.retrieve.channels.base import SearchContext
from app.rag.retrieve.channels.intent_directed_channel import IntentDirectedSearchChannel
from app.rag.retrieve.multi_channel_retrieval_engine import MultiChannelRetrievalEngine
from app.rag.retrieve.retrieval_engine import RetrievalEngine
from app.rag.rewrite import RewriteResult


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


@dataclass
class SavedAssistant:
    message_id: str
    title: str


class CapturingMemoryService:
    def __init__(self) -> None:
        self.user_messages: list[str] = []
        self.assistant_messages: list[str] = []

    async def load_history(self, *_: object) -> list[ChatMessage]:
        return [ChatMessage(role="assistant", content="历史回答")]

    async def append_user_message(self, _: str, __: str, content: str) -> SavedAssistant:
        self.user_messages.append(content)
        return SavedAssistant(message_id="user-msg", title="测试标题")

    async def append_assistant_message(self, _: str, __: str, content: str) -> SavedAssistant:
        self.assistant_messages.append(content)
        return SavedAssistant(message_id="assistant-msg", title="测试标题")


class CapturingRewriteService:
    async def rewrite_with_split(self, question: str, _: list[ChatMessage]) -> RewriteResult:
        return RewriteResult(
            original_question=question,
            rewritten_question="Ragent 支持什么向量检索",
            sub_questions=["Ragent 支持什么向量检索"],
        )


class CapturingIntentResolver:
    async def resolve(self, _: RewriteResult) -> IntentResolution:
        return IntentResolution(
            matches=[
                IntentMatch(
                    intent_id="intent-1",
                    intent_code="rag.vector",
                    name="向量检索",
                    confidence=0.9,
                    kb_id="kb-1",
                ),
            ],
        )


class CapturingRetrievalEngine:
    def __init__(self) -> None:
        self.kwargs: dict | None = None

    async def retrieve(self, **kwargs: object) -> list[RetrievedChunk]:
        self.kwargs = kwargs
        return [RetrievedChunk(id="chunk-1", content="命中意图知识", score=0.88)]


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


@pytest.mark.asyncio
async def test_stream_chat_pipeline_loads_memory_rewrites_intents_and_persists_answer() -> None:
    llm_service = CapturingLLMService()
    memory_service = CapturingMemoryService()
    retrieval_engine = CapturingRetrievalEngine()
    pipeline = StreamChatPipeline(
        llm_service=llm_service,
        retrieval_engine=retrieval_engine,
        memory_service=memory_service,
        query_rewrite_service=CapturingRewriteService(),
        intent_resolver=CapturingIntentResolver(),
    )
    context = StreamChatContext(
        question="Ragent 支持什么检索？",
        conversation_id="conv-1",
        task_id="task-1",
        user_id="user-1",
    )

    deltas = [delta async for delta in pipeline.execute(context)]

    assert deltas == ["已基于知识库回答"]
    assert memory_service.user_messages == ["Ragent 支持什么检索？"]
    assert memory_service.assistant_messages == ["已基于知识库回答"]
    assert context.assistant_message_id == "assistant-msg"
    assert context.title == "测试标题"
    assert retrieval_engine.kwargs is not None
    assert retrieval_engine.kwargs["query"] == "Ragent 支持什么向量检索"
    assert retrieval_engine.kwargs["original_query"] == "Ragent 支持什么检索？"
    assert retrieval_engine.kwargs["intents"][0].intent_code == "rag.vector"
    assert "历史回答" in llm_service.request.messages[1].content
    assert "向量检索(0.90)" in llm_service.request.messages[0].content


@pytest.mark.asyncio
async def test_intent_directed_channel_searches_each_knowledge_intent() -> None:
    class FakeVectorStore:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        async def search(self, query: str, top_k: int, kb_id: str | None = None):
            self.calls.append({"query": query, "top_k": top_k, "kb_id": kb_id})
            return [RetrievedChunk(id="chunk-1", content="知识", score=0.8, metadata={"docName": "文档"})]

    vector_store = FakeVectorStore()
    channel = IntentDirectedSearchChannel(vector_store)
    chunks = await channel.search(
        SearchContext(
            query="报销流程",
            top_k=5,
            intents=[
                IntentMatch(
                    intent_id="intent-1",
                    intent_code="finance.invoice",
                    name="财务报销",
                    confidence=0.75,
                    kb_id="kb-fin",
                    top_k=3,
                ),
            ],
        ),
    )

    assert vector_store.calls == [{"query": "报销流程", "top_k": 3, "kb_id": "kb-fin"}]
    assert chunks[0].score == pytest.approx(0.6)
    assert chunks[0].metadata["intentName"] == "财务报销"
    assert chunks[0].metadata["channel"] == "intent_directed"


@pytest.mark.asyncio
async def test_retrieval_engine_merges_mcp_context() -> None:
    class EmptyChannel:
        name = "empty"

        async def search(self, _: SearchContext) -> list[RetrievedChunk]:
            return []

    engine = RetrievalEngine(MultiChannelRetrievalEngine([EmptyChannel()]), mcp_service=MCPService())

    result = await engine.retrieve_with_context(
        query="帮我查上海未来2天天气预报",
        intents=[
            IntentMatch(
                intent_id="intent-weather",
                intent_code="weather",
                name="天气查询",
                confidence=0.9,
                mcp_tool_id="weather_query",
            ),
        ],
    )

    assert result.chunks == []
    assert result.mcp_responses[0].success is True
    assert "上海" in result.mcp_context
    assert "天气" in result.mcp_context


def test_prompt_service_includes_mcp_context() -> None:
    messages = PromptService().build_messages(
        "上海天气怎么样？",
        [],
        mcp_responses=[MCPResponse.ok("weather_query", "上海今日晴")],
    )

    assert "MCP 工具调用结果" in messages[0].content
    assert "上海今日晴" in messages[0].content


@pytest.mark.asyncio
async def test_retrieval_engine_reranks_multi_channel_candidates() -> None:
    class FixedChannel:
        name = "fixed"

        async def search(self, _: SearchContext) -> list[RetrievedChunk]:
            return [
                RetrievedChunk(id="chunk-low", content="低相关", score=0.2),
                RetrievedChunk(id="chunk-high", content="高相关", score=0.9),
            ]

    class FakeRerankService:
        async def rerank(self, request):
            assert request.top_n == 1
            return RerankResponse(
                documents=[
                    RerankDocument(id="chunk-low", content="低相关", score=0.99),
                ],
                model="fake-rerank",
            )

    engine = RetrievalEngine(
        MultiChannelRetrievalEngine([FixedChannel()]),
        rerank_service=FakeRerankService(),
    )

    result = await engine.retrieve_with_context(query="问题", top_k=1)

    assert [chunk.id for chunk in result.chunks] == ["chunk-low"]
    assert result.chunks[0].score == pytest.approx(0.99)
