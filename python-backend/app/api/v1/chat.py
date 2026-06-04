import asyncio
import json
from collections.abc import AsyncIterator
from functools import lru_cache
from time import perf_counter
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from app.api.deps import get_current_user
from app.common.ids import generate_id
from app.core.config import settings
from app.core.exceptions import RagentException
from app.core.responses import ApiResponse, success
from app.db.session import get_db_session
from app.infra_ai.chat import RoutingLLMService
from app.infra_ai.config import default_chat_targets, default_embedding_targets
from app.infra_ai.embedding import RoutingEmbeddingService
from app.mcp import MCPService
from app.models import User
from app.rag.intent import IntentResolver
from app.rag.memory import ConversationMemoryService
from app.rag.pipeline import StreamChatContext, StreamChatPipeline
from app.rag.rate_limit import ChatQueueLimiter, QueueStatus, RedisQueueBackend
from app.rag.rewrite import QueryRewriteService
from app.rag.retrieve import PgVectorStoreService
from app.rag.retrieve.channels import IntentDirectedSearchChannel, VectorGlobalSearchChannel
from app.rag.retrieve.multi_channel_retrieval_engine import MultiChannelRetrievalEngine
from app.rag.retrieve.retrieval_engine import RetrievalEngine
from app.rag.stream import stream_task_manager
from app.schemas.chat import ChatQuery, StopChatRequest, StopChatResponse
from app.services.trace_service import TraceService

router = APIRouter(prefix="/rag/v3", tags=["rag"])


def get_llm_service() -> RoutingLLMService:
    return RoutingLLMService(default_chat_targets())


def get_embedding_service() -> RoutingEmbeddingService:
    return RoutingEmbeddingService(default_embedding_targets())


def get_retrieval_engine(
    session: AsyncSession = Depends(get_db_session),
    embedding_service: RoutingEmbeddingService = Depends(get_embedding_service),
) -> RetrievalEngine:
    vector_store = PgVectorStoreService(session=session, embedding_service=embedding_service)
    return RetrievalEngine(
        MultiChannelRetrievalEngine(
            [
                IntentDirectedSearchChannel(vector_store),
                VectorGlobalSearchChannel(vector_store),
            ],
        ),
        mcp_service=MCPService(),
    )


def get_trace_service(session: AsyncSession = Depends(get_db_session)) -> TraceService:
    return TraceService(session)


def get_memory_service(session: AsyncSession = Depends(get_db_session)) -> ConversationMemoryService:
    return ConversationMemoryService(session)


def get_query_rewrite_service(session: AsyncSession = Depends(get_db_session)) -> QueryRewriteService:
    return QueryRewriteService(session)


def get_intent_resolver(session: AsyncSession = Depends(get_db_session)) -> IntentResolver:
    return IntentResolver(session)


@lru_cache
def get_chat_queue_limiter() -> ChatQueueLimiter:
    if not settings.rag_queue_limit_enabled:
        return ChatQueueLimiter.disabled()
    return ChatQueueLimiter(
        enabled=True,
        backend=RedisQueueBackend(settings.redis_url, settings.rag_queue_key_prefix),
        max_concurrency=settings.rag_queue_max_concurrency,
        timeout_seconds=settings.rag_queue_timeout_seconds,
        poll_interval_seconds=settings.rag_queue_poll_interval_seconds,
        active_ttl_seconds=settings.rag_queue_active_ttl_seconds,
    )


@router.get("/chat")
async def stream_chat_api(
    question: str = Query(..., min_length=1),
    conversation_id: str | None = Query(default=None, alias="conversationId"),
    conversation_id_fallback: str | None = Query(default=None, alias="conversation_id"),
    deep_thinking: bool = Query(default=False, alias="deepThinking"),
    deep_thinking_fallback: bool | None = Query(default=None, alias="deep_thinking"),
    user: User = Depends(get_current_user),
    llm_service: RoutingLLMService = Depends(get_llm_service),
    retrieval_engine: RetrievalEngine = Depends(get_retrieval_engine),
    memory_service: ConversationMemoryService = Depends(get_memory_service),
    query_rewrite_service: QueryRewriteService = Depends(get_query_rewrite_service),
    intent_resolver: IntentResolver = Depends(get_intent_resolver),
    trace_service: TraceService = Depends(get_trace_service),
    queue_limiter: ChatQueueLimiter = Depends(get_chat_queue_limiter),
) -> StreamingResponse:
    return _create_chat_stream(
        ChatQuery(
            question=question,
            conversation_id=conversation_id or conversation_id_fallback,
            deep_thinking=deep_thinking if deep_thinking_fallback is None else deep_thinking_fallback,
        ),
        user,
        llm_service,
        retrieval_engine,
        memory_service,
        query_rewrite_service,
        intent_resolver,
        trace_service,
        queue_limiter,
    )


@router.post("/chat")
async def stream_chat_post_api(
    request: ChatQuery,
    user: User = Depends(get_current_user),
    llm_service: RoutingLLMService = Depends(get_llm_service),
    retrieval_engine: RetrievalEngine = Depends(get_retrieval_engine),
    memory_service: ConversationMemoryService = Depends(get_memory_service),
    query_rewrite_service: QueryRewriteService = Depends(get_query_rewrite_service),
    intent_resolver: IntentResolver = Depends(get_intent_resolver),
    trace_service: TraceService = Depends(get_trace_service),
    queue_limiter: ChatQueueLimiter = Depends(get_chat_queue_limiter),
) -> StreamingResponse:
    return _create_chat_stream(
        request,
        user,
        llm_service,
        retrieval_engine,
        memory_service,
        query_rewrite_service,
        intent_resolver,
        trace_service,
        queue_limiter,
    )


def _create_chat_stream(
    request: ChatQuery,
    user: User,
    llm_service: RoutingLLMService,
    retrieval_engine: RetrievalEngine | None,
    memory_service: ConversationMemoryService | None,
    query_rewrite_service: QueryRewriteService | None,
    intent_resolver: IntentResolver | None,
    trace_service: TraceService | None,
    queue_limiter: ChatQueueLimiter,
) -> StreamingResponse:
    task_id = uuid4().hex
    context = StreamChatContext(
        question=request.question,
        conversation_id=request.conversation_id or generate_id(),
        task_id=task_id,
        user_id=str(user.id),
        deep_thinking=request.deep_thinking,
    )
    queue: asyncio.Queue[dict] = asyncio.Queue()
    task = asyncio.create_task(
        _run_pipeline(
            context,
            llm_service,
            retrieval_engine,
            memory_service,
            query_rewrite_service,
            intent_resolver,
            trace_service,
            queue_limiter,
            queue,
        ),
    )
    stream_task_manager.register(task_id, task)
    return StreamingResponse(
        _event_stream(queue),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/stop", response_model=ApiResponse[StopChatResponse])
async def stop_chat_api(
    request: StopChatRequest | None = Body(default=None),
    task_id: str | None = Query(default=None, alias="taskId"),
    task_id_fallback: str | None = Query(default=None, alias="task_id"),
    _: User = Depends(get_current_user),
) -> ApiResponse[StopChatResponse]:
    resolved_task_id = task_id or task_id_fallback or (request.task_id if request is not None else None)
    if not resolved_task_id:
        raise RagentException(message="taskId 不能为空", code="40001", status_code=400)
    stopped = stream_task_manager.cancel(resolved_task_id)
    return success(StopChatResponse(stopped=stopped))


async def _run_pipeline(
    context: StreamChatContext,
    llm_service: RoutingLLMService,
    retrieval_engine: RetrievalEngine | None,
    memory_service: ConversationMemoryService | None,
    query_rewrite_service: QueryRewriteService | None,
    intent_resolver: IntentResolver | None,
    trace_service: TraceService | None,
    queue_limiter: ChatQueueLimiter,
    queue: asyncio.Queue[dict],
) -> None:
    pipeline = StreamChatPipeline(
        llm_service,
        retrieval_engine=retrieval_engine,
        memory_service=memory_service,
        query_rewrite_service=query_rewrite_service,
        intent_resolver=intent_resolver,
    )
    trace_id = None
    started_at = perf_counter()
    try:
        if trace_service is not None:
            trace_id = await trace_service.start_run(
                trace_name="rag_chat",
                task_id=context.task_id,
                user_id=context.user_id,
                conversation_id=context.conversation_id,
            )
        await queue.put({"__event": "meta", "conversationId": context.conversation_id, "taskId": context.task_id})
        permit = await queue_limiter.acquire(
            context.task_id,
            on_status=lambda status: _put_queue_status(queue, context, status),
        )
        if not permit.acquired:
            await _handle_queue_timeout(queue, context, permit.reason)
            if trace_service is not None and trace_id is not None:
                await trace_service.record_node(
                    trace_id=trace_id,
                    node_name="chat_queue_limiter",
                    node_type="QUEUE_LIMITER",
                    status="TIMEOUT",
                    duration_ms=TraceService.elapsed_ms(started_at),
                    error_message=permit.reason,
                )
                await trace_service.finish_run(trace_id, status="FAILED", error_message=permit.reason)
            return
        try:
            async for delta in pipeline.execute(context):
                await queue.put(
                    {
                        "__event": "message",
                        "type": "response",
                        "delta": delta,
                        "conversationId": context.conversation_id,
                        "taskId": context.task_id,
                    },
                )
        finally:
            await permit.release()
        if trace_service is not None and trace_id is not None:
            await trace_service.record_node(
                trace_id=trace_id,
                node_name="stream_chat_pipeline",
                node_type="PIPELINE",
                status="SUCCESS",
                duration_ms=TraceService.elapsed_ms(started_at),
            )
            await trace_service.finish_run(trace_id, status="SUCCESS")
        await queue.put(
            {
                "__event": "finish",
                "conversationId": context.conversation_id,
                "taskId": context.task_id,
                "messageId": context.assistant_message_id,
                "title": context.title,
            },
        )
    except asyncio.CancelledError:
        if trace_service is not None and trace_id is not None:
            await trace_service.finish_run(trace_id, status="CANCELLED")
        await queue.put(
            {
                "__event": "cancel",
                "conversationId": context.conversation_id,
                "taskId": context.task_id,
                "messageId": None,
                "title": None,
            },
        )
        raise
    except Exception as exc:
        if trace_service is not None and trace_id is not None:
            await trace_service.record_node(
                trace_id=trace_id,
                node_name="stream_chat_pipeline",
                node_type="PIPELINE",
                status="FAILED",
                duration_ms=TraceService.elapsed_ms(started_at),
                error_message=str(exc),
            )
            await trace_service.finish_run(trace_id, status="FAILED", error_message=str(exc))
        await queue.put(
            {
                "__event": "error",
                "error": str(exc),
                "conversationId": context.conversation_id,
                "taskId": context.task_id,
            },
        )
    finally:
        await queue.put({"__event": "done"})
        await queue.put({"__event": "__end"})


async def _put_queue_status(
    queue: asyncio.Queue[dict],
    context: StreamChatContext,
    status: QueueStatus,
) -> None:
    await queue.put(
        {
            "__event": "queue",
            "type": "queue",
            "status": status.status,
            "position": status.position,
            "waitingSeconds": status.waiting_seconds,
            "timeoutSeconds": status.timeout_seconds,
            "maxConcurrency": status.max_concurrency,
            "conversationId": context.conversation_id,
            "taskId": context.task_id,
        },
    )


async def _handle_queue_timeout(
    queue: asyncio.Queue[dict],
    context: StreamChatContext,
    reason: str | None,
) -> None:
    await queue.put(
        {
            "__event": "message",
            "type": "response",
            "delta": "系统繁忙，请稍后重试。",
            "conversationId": context.conversation_id,
            "taskId": context.task_id,
            "reason": reason,
        },
    )
    await queue.put(
        {
            "__event": "finish",
            "conversationId": context.conversation_id,
            "taskId": context.task_id,
            "messageId": None,
            "title": None,
        },
    )


async def _event_stream(queue: asyncio.Queue[dict]) -> AsyncIterator[str]:
    while True:
        payload = await queue.get()
        event_name = payload.pop("__event", "message")
        if event_name == "__end":
            break
        yield f"event: {event_name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
