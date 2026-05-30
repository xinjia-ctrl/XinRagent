import asyncio
import json
from collections.abc import AsyncIterator
from time import perf_counter
from uuid import uuid4

from fastapi import APIRouter, Depends, Query
from starlette.responses import StreamingResponse

from app.api.deps import get_current_user
from app.core.responses import ApiResponse, success
from app.infra_ai.chat import RoutingLLMService
from app.infra_ai.config import default_chat_targets, default_embedding_targets
from app.infra_ai.embedding import RoutingEmbeddingService
from app.models import User
from app.db.session import get_db_session
from app.rag.pipeline import StreamChatContext, StreamChatPipeline
from app.rag.retrieve import PgVectorStoreService
from app.rag.retrieve.channels import VectorGlobalSearchChannel
from app.rag.retrieve.multi_channel_retrieval_engine import MultiChannelRetrievalEngine
from app.rag.retrieve.retrieval_engine import RetrievalEngine
from app.rag.stream import stream_task_manager
from app.schemas.chat import StopChatRequest, StopChatResponse
from sqlalchemy.ext.asyncio import AsyncSession
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
    channel = VectorGlobalSearchChannel(vector_store)
    return RetrievalEngine(MultiChannelRetrievalEngine([channel]))


def get_trace_service(session: AsyncSession = Depends(get_db_session)) -> TraceService:
    return TraceService(session)


@router.get("/chat")
async def stream_chat_api(
    question: str = Query(..., min_length=1),
    conversation_id: str | None = Query(default=None, alias="conversationId"),
    deep_thinking: bool = Query(default=False, alias="deepThinking"),
    user: User = Depends(get_current_user),
    llm_service: RoutingLLMService = Depends(get_llm_service),
    retrieval_engine: RetrievalEngine = Depends(get_retrieval_engine),
    trace_service: TraceService = Depends(get_trace_service),
) -> StreamingResponse:
    task_id = uuid4().hex
    context = StreamChatContext(
        question=question,
        conversation_id=conversation_id,
        task_id=task_id,
        user_id=str(user.id),
        deep_thinking=deep_thinking,
    )
    queue: asyncio.Queue[dict] = asyncio.Queue()
    task = asyncio.create_task(_run_pipeline(context, llm_service, retrieval_engine, trace_service, queue))
    stream_task_manager.register(task_id, task)
    return StreamingResponse(
        _event_stream(queue),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/stop", response_model=ApiResponse[StopChatResponse])
async def stop_chat_api(
    request: StopChatRequest,
    _: User = Depends(get_current_user),
) -> ApiResponse[StopChatResponse]:
    stopped = stream_task_manager.cancel(request.task_id)
    return success(StopChatResponse(stopped=stopped))


async def _run_pipeline(
    context: StreamChatContext,
    llm_service: RoutingLLMService,
    retrieval_engine: RetrievalEngine | None,
    trace_service: TraceService | None,
    queue: asyncio.Queue[dict],
) -> None:
    pipeline = StreamChatPipeline(llm_service, retrieval_engine=retrieval_engine)
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
        await queue.put({"type": "start", "conversationId": context.conversation_id, "taskId": context.task_id})
        async for delta in pipeline.execute(context):
            await queue.put(
                {
                    "type": "delta",
                    "content": delta,
                    "conversationId": context.conversation_id,
                    "taskId": context.task_id,
                },
            )
        if trace_service is not None and trace_id is not None:
            await trace_service.record_node(
                trace_id=trace_id,
                node_name="stream_chat_pipeline",
                node_type="PIPELINE",
                status="SUCCESS",
                duration_ms=TraceService.elapsed_ms(started_at),
            )
            await trace_service.finish_run(trace_id, status="SUCCESS")
        await queue.put({"type": "complete", "conversationId": context.conversation_id, "taskId": context.task_id})
    except asyncio.CancelledError:
        if trace_service is not None and trace_id is not None:
            await trace_service.finish_run(trace_id, status="CANCELLED")
        await queue.put({"type": "stopped", "conversationId": context.conversation_id, "taskId": context.task_id})
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
                "type": "error",
                "message": str(exc),
                "conversationId": context.conversation_id,
                "taskId": context.task_id,
            },
        )
    finally:
        await queue.put({"type": "done"})


async def _event_stream(queue: asyncio.Queue[dict]) -> AsyncIterator[str]:
    while True:
        payload = await queue.get()
        if payload.get("type") == "done":
            break
        yield f"event: message\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
