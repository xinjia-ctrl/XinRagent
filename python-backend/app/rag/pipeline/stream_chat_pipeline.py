from collections.abc import AsyncIterator
import logging
from time import perf_counter

from app.core.config import settings
from app.infra_ai.chat import ChatMessage, ChatRequest, RoutingLLMService
from app.rag.intent import IntentResolver
from app.rag.memory import ConversationMemoryService
from app.rag.pipeline.stream_chat_context import StreamChatContext
from app.rag.prompt import PromptService
from app.rag.retrieve.retrieval_engine import RetrievalEngine
from app.rag.rewrite import QueryRewriteService

logger = logging.getLogger(__name__)


class StreamChatPipeline:
    def __init__(
        self,
        llm_service: RoutingLLMService,
        retrieval_engine: RetrievalEngine | None = None,
        memory_service: ConversationMemoryService | None = None,
        query_rewrite_service: QueryRewriteService | None = None,
        intent_resolver: IntentResolver | None = None,
        prompt_service: PromptService | None = None,
    ) -> None:
        self.llm_service = llm_service
        self.retrieval_engine = retrieval_engine
        self.memory_service = memory_service
        self.query_rewrite_service = query_rewrite_service or QueryRewriteService()
        self.intent_resolver = intent_resolver or IntentResolver()
        self.prompt_service = prompt_service or PromptService()

    async def execute(self, context: StreamChatContext) -> AsyncIterator[str]:
        context.history = await self._load_history(context)
        await self._append_user_message(context)

        context.rewrite_result = await self.query_rewrite_service.rewrite_with_split(
            context.question,
            context.history,
        )
        context.intent_resolution = await self.intent_resolver.resolve(context.rewrite_result)

        if context.intent_resolution.guidance_prompt:
            async for delta in self._stream_plain_answer(context, context.intent_resolution.guidance_prompt):
                yield delta
            return

        if context.intent_resolution.is_system_only:
            async for delta in self._stream_system_answer(context):
                yield delta
            return

        chunks = []
        mcp_responses = []
        if self.retrieval_engine is not None:
            retrieve_kwargs = {
                "query": context.rewrite_result.rewritten_question,
                "original_query": context.question,
                "intents": [*context.intent_resolution.knowledge_matches, *context.intent_resolution.mcp_matches],
                "conversation_id": context.conversation_id,
                "user_id": context.user_id,
            }
            if hasattr(self.retrieval_engine, "retrieve_with_context"):
                retrieval_result = await self.retrieval_engine.retrieve_with_context(**retrieve_kwargs)
                chunks = retrieval_result.chunks
                mcp_responses = retrieval_result.mcp_responses
            else:
                chunks = await self.retrieval_engine.retrieve(**retrieve_kwargs)
        context.retrieved_chunks = chunks
        context.mcp_responses = mcp_responses

        request = ChatRequest(
            messages=self.prompt_service.build_messages(
                context.question,
                chunks,
                history=context.history,
                rewritten_question=context.rewrite_result.rewritten_question,
                sub_questions=context.rewrite_result.sub_questions,
                intents=context.intent_resolution.matches,
                mcp_responses=mcp_responses,
            ),
            model=self._chat_model(context),
            stream=True,
            temperature=0.0,
            extra_body=self._chat_extra_body(context),
        )
        answer_parts: list[str] = []
        thinking_parts: list[str] = []
        thinking_started_at = perf_counter()
        async for chunk in self.llm_service.stream(request):
            if context.deep_thinking and chunk.thinking_delta:
                thinking_parts.append(chunk.thinking_delta)
            if chunk.delta:
                answer_parts.append(chunk.delta)
                yield chunk.delta
        self._capture_thinking(context, thinking_parts, thinking_started_at)
        await self._append_assistant_message(
            context,
            "".join(answer_parts),
            thinking_content=context.thinking_content,
            thinking_duration=context.thinking_duration,
        )

    async def _stream_plain_answer(
        self,
        context: StreamChatContext,
        answer: str,
    ) -> AsyncIterator[str]:
        yield answer
        await self._append_assistant_message(context, answer)

    async def _stream_system_answer(self, context: StreamChatContext) -> AsyncIterator[str]:
        assert context.rewrite_result is not None
        assert context.intent_resolution is not None
        custom_prompt = next(
            (
                intent.prompt_template
                for intent in context.intent_resolution.system_matches
                if intent.prompt_template
            ),
            None,
        )
        system_prompt = custom_prompt or "你是 Ragent Python 后端的 AI 助手，请直接回答系统类问题。"
        messages = self.prompt_service.build_messages(
            context.question,
            [],
            history=context.history,
            rewritten_question=context.rewrite_result.rewritten_question,
            intents=context.intent_resolution.matches,
        )
        messages[0] = ChatMessage(role="system", content=system_prompt)
        request = ChatRequest(
            messages=messages,
            model=self._chat_model(context),
            stream=True,
            temperature=0.7,
            extra_body=self._chat_extra_body(context),
        )
        answer_parts: list[str] = []
        thinking_parts: list[str] = []
        thinking_started_at = perf_counter()
        async for chunk in self.llm_service.stream(request):
            if context.deep_thinking and chunk.thinking_delta:
                thinking_parts.append(chunk.thinking_delta)
            if chunk.delta:
                answer_parts.append(chunk.delta)
                yield chunk.delta
        self._capture_thinking(context, thinking_parts, thinking_started_at)
        await self._append_assistant_message(
            context,
            "".join(answer_parts),
            thinking_content=context.thinking_content,
            thinking_duration=context.thinking_duration,
        )

    async def _load_history(self, context: StreamChatContext):
        if self.memory_service is None:
            return []
        return await self.memory_service.load_history(context.conversation_id, context.user_id)

    async def _append_user_message(self, context: StreamChatContext) -> None:
        if self.memory_service is None:
            return
        appended = await self.memory_service.append_user_message(
            context.conversation_id,
            context.user_id,
            context.question,
        )
        if appended and appended.title:
            context.title = appended.title

    async def _append_assistant_message(
        self,
        context: StreamChatContext,
        answer: str,
        thinking_content: str | None = None,
        thinking_duration: int | None = None,
    ) -> None:
        if self.memory_service is None or not answer:
            return
        if thinking_content:
            appended = await self.memory_service.append_assistant_message(
                context.conversation_id,
                context.user_id,
                answer,
                thinking_content=thinking_content,
                thinking_duration=thinking_duration,
            )
        else:
            appended = await self.memory_service.append_assistant_message(
                context.conversation_id,
                context.user_id,
                answer,
            )
        if appended is None:
            return
        context.assistant_message_id = appended.message_id
        if appended.title:
            context.title = appended.title
        if hasattr(self.memory_service, "maybe_compact_history"):
            try:
                await self.memory_service.maybe_compact_history(context.conversation_id, context.user_id)
            except Exception as exc:
                logger.warning("conversation memory compaction failed: %s", exc)

    @staticmethod
    def _chat_model(context: StreamChatContext) -> str:
        return settings.ai_deep_thinking_model if context.deep_thinking else settings.ai_chat_default_model

    @staticmethod
    def _chat_extra_body(context: StreamChatContext) -> dict | None:
        if not context.deep_thinking:
            return None
        return {
            "enable_thinking": True,
            "thinking": {"type": "enabled"},
        }

    @staticmethod
    def _capture_thinking(context: StreamChatContext, thinking_parts: list[str], started_at: float) -> None:
        if not thinking_parts:
            return
        context.thinking_content = "".join(thinking_parts)
        context.thinking_duration = int((perf_counter() - started_at) * 1000)
