import asyncio
import json
from collections.abc import AsyncIterator
from uuid import uuid4

from fastapi import APIRouter, Depends, Query
from starlette.responses import StreamingResponse

from app.api.deps import get_current_user
from app.core.responses import ApiResponse, success
from app.infra_ai.chat import RoutingLLMService
from app.infra_ai.config import default_chat_targets
from app.models import User
from app.rag.pipeline import StreamChatContext, StreamChatPipeline
from app.rag.stream import stream_task_manager
from app.schemas.chat import StopChatRequest, StopChatResponse

router = APIRouter(prefix="/rag/v3", tags=["rag"])


def get_llm_service() -> RoutingLLMService:
    return RoutingLLMService(default_chat_targets())


@router.get("/chat")
async def stream_chat_api(
    question: str = Query(..., min_length=1),
    conversation_id: str | None = Query(default=None, alias="conversationId"),
    deep_thinking: bool = Query(default=False, alias="deepThinking"),
    user: User = Depends(get_current_user),
    llm_service: RoutingLLMService = Depends(get_llm_service),
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
    task = asyncio.create_task(_run_pipeline(context, llm_service, queue))
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
    queue: asyncio.Queue[dict],
) -> None:
    pipeline = StreamChatPipeline(llm_service)
    try:
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
        await queue.put({"type": "complete", "conversationId": context.conversation_id, "taskId": context.task_id})
    except asyncio.CancelledError:
        await queue.put({"type": "stopped", "conversationId": context.conversation_id, "taskId": context.task_id})
        raise
    except Exception as exc:
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
