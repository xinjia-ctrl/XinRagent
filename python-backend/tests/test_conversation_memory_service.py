from unittest.mock import AsyncMock

import pytest

from app.infra_ai.chat import ChatRequest, ChatResponse
from app.rag.memory.conversation_memory_service import ConversationMemoryService, SummaryRecord


class SummaryLLMService:
    def __init__(self) -> None:
        self.request: ChatRequest | None = None

    async def complete(self, request: ChatRequest) -> ChatResponse:
        self.request = request
        return ChatResponse(content="用户关注 Milvus 入库验证，需要继续比较 pgvector。", model=request.model)


@pytest.mark.asyncio
async def test_memory_service_compacts_old_messages_with_llm_summary(monkeypatch) -> None:
    session = AsyncMock()
    llm_service = SummaryLLMService()
    service = ConversationMemoryService(
        session,
        llm_service=llm_service,
        summary_enabled=True,
        summary_start_messages=3,
        keep_recent_messages=1,
        summary_max_chars=80,
    )
    replace_summary = AsyncMock()
    monkeypatch.setattr(service, "_count_messages", AsyncMock(return_value=4))
    monkeypatch.setattr(
        service,
        "_load_latest_summary_record",
        AsyncMock(return_value=SummaryRecord(content="用户之前在复刻 Ragent。", last_message_id="msg-0")),
    )
    monkeypatch.setattr(
        service,
        "_load_messages_for_summary",
        AsyncMock(
            return_value=[
                {"id": "msg-1", "role": "user", "content": "Milvus 要真实验证"},
                {"id": "msg-2", "role": "assistant", "content": "需要入库检索删除重建测试"},
                {"id": "msg-3", "role": "user", "content": "还要比较 pgvector"},
            ],
        ),
    )
    monkeypatch.setattr(service, "_replace_summary", replace_summary)

    await service.maybe_compact_history("conv-1", "user-1")

    assert llm_service.request is not None
    assert "旧摘要" in llm_service.request.messages[1].content
    replace_summary.assert_awaited_once_with(
        "conv-1",
        "user-1",
        "msg-3",
        "用户关注 Milvus 入库验证，需要继续比较 pgvector。",
    )


@pytest.mark.asyncio
async def test_memory_service_skips_when_summary_already_covers_messages(monkeypatch) -> None:
    service = ConversationMemoryService(
        AsyncMock(),
        summary_enabled=True,
        summary_start_messages=3,
        keep_recent_messages=1,
    )
    replace_summary = AsyncMock()
    monkeypatch.setattr(service, "_count_messages", AsyncMock(return_value=4))
    monkeypatch.setattr(
        service,
        "_load_latest_summary_record",
        AsyncMock(return_value=SummaryRecord(content="已有摘要", last_message_id="msg-3")),
    )
    monkeypatch.setattr(
        service,
        "_load_messages_for_summary",
        AsyncMock(return_value=[{"id": "msg-3", "role": "assistant", "content": "已摘要"}]),
    )
    monkeypatch.setattr(service, "_replace_summary", replace_summary)

    await service.maybe_compact_history("conv-1", "user-1")

    replace_summary.assert_not_awaited()
