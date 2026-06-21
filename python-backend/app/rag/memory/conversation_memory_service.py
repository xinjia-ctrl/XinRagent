from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.ids import generate_id
from app.core.config import settings
from app.infra_ai.chat import ChatMessage, ChatRequest, RoutingLLMService


@dataclass(frozen=True)
class AppendedMessage:
    message_id: str
    title: str | None = None


@dataclass(frozen=True)
class SummaryRecord:
    content: str
    last_message_id: str


class ConversationMemoryService:
    def __init__(
        self,
        session: AsyncSession,
        history_limit: int = 10,
        *,
        llm_service: RoutingLLMService | None = None,
        summary_enabled: bool | None = None,
        summary_start_messages: int | None = None,
        keep_recent_messages: int | None = None,
        summary_max_chars: int | None = None,
    ) -> None:
        self.session = session
        self.history_limit = history_limit
        self.llm_service = llm_service
        self.summary_enabled = settings.rag_memory_summary_enabled if summary_enabled is None else summary_enabled
        self.summary_start_messages = summary_start_messages or settings.rag_memory_summary_start_messages
        self.keep_recent_messages = keep_recent_messages or settings.rag_memory_summary_keep_recent_messages
        self.summary_max_chars = summary_max_chars or settings.rag_memory_summary_max_chars

    async def load_history(self, conversation_id: str | None, user_id: str | None) -> list[ChatMessage]:
        if not conversation_id or not user_id:
            return []

        summary = await self._load_latest_summary_record(conversation_id, user_id)
        result = await self.session.execute(
            text(
                """
                SELECT role, content, thinking_content
                FROM t_message
                WHERE conversation_id = :conversation_id
                  AND user_id = :user_id
                  AND deleted = 0
                ORDER BY create_time DESC
                LIMIT :limit
                """,
            ),
            {
                "conversation_id": conversation_id,
                "user_id": user_id,
                "limit": self.history_limit,
            },
        )
        rows = list(reversed(result.mappings().all()))
        messages = [ChatMessage(role=row["role"], content=row["content"]) for row in rows]
        if summary:
            messages.insert(0, ChatMessage(role="system", content=f"以下是此前对话摘要：{summary.content}"))
        return messages

    async def append_user_message(
        self,
        conversation_id: str | None,
        user_id: str | None,
        content: str,
    ) -> AppendedMessage | None:
        return await self.append_message(conversation_id, user_id, "user", content)

    async def append_assistant_message(
        self,
        conversation_id: str | None,
        user_id: str | None,
        content: str,
        thinking_content: str | None = None,
        thinking_duration: int | None = None,
    ) -> AppendedMessage | None:
        return await self.append_message(
            conversation_id,
            user_id,
            "assistant",
            content,
            thinking_content=thinking_content,
            thinking_duration=thinking_duration,
        )

    async def append_message(
        self,
        conversation_id: str | None,
        user_id: str | None,
        role: str,
        content: str,
        thinking_content: str | None = None,
        thinking_duration: int | None = None,
    ) -> AppendedMessage | None:
        if not conversation_id or not user_id or not content:
            return None

        title = await self._ensure_conversation(conversation_id, user_id, content)
        message_id = generate_id()
        await self.session.execute(
            text(
                """
                INSERT INTO t_message (
                    id, conversation_id, user_id, role, content,
                    thinking_content, thinking_duration
                )
                VALUES (
                    :id, :conversation_id, :user_id, :role, :content,
                    :thinking_content, :thinking_duration
                )
                """,
            ),
            {
                "id": message_id,
                "conversation_id": conversation_id,
                "user_id": user_id,
                "role": role,
                "content": content,
                "thinking_content": thinking_content,
                "thinking_duration": thinking_duration,
            },
        )
        await self.session.execute(
            text(
                """
                UPDATE t_conversation
                SET last_time = CURRENT_TIMESTAMP,
                    update_time = CURRENT_TIMESTAMP
                WHERE conversation_id = :conversation_id
                  AND user_id = :user_id
                  AND deleted = 0
                """,
            ),
            {"conversation_id": conversation_id, "user_id": user_id},
        )
        await self.session.commit()
        return AppendedMessage(message_id=message_id, title=title)

    async def maybe_compact_history(self, conversation_id: str | None, user_id: str | None) -> None:
        if not self.summary_enabled or not conversation_id or not user_id:
            return

        total = await self._count_messages(conversation_id, user_id)
        if total < self.summary_start_messages:
            return

        summary_messages = await self._load_messages_for_summary(conversation_id, user_id, total)
        if not summary_messages:
            return

        latest_summary = await self._load_latest_summary_record(conversation_id, user_id)
        last_message_id = str(summary_messages[-1]["id"])
        if latest_summary is not None and latest_summary.last_message_id == last_message_id:
            return

        summary_content = await self._summarize_messages(latest_summary, summary_messages)
        await self._replace_summary(conversation_id, user_id, last_message_id, summary_content)

    async def _ensure_conversation(self, conversation_id: str, user_id: str, seed_content: str) -> str:
        title = self._build_title(seed_content)
        conversation_pk = generate_id()
        await self.session.execute(
            text(
                """
                INSERT INTO t_conversation (
                    id, conversation_id, user_id, title, last_time
                )
                VALUES (
                    :id, :conversation_id, :user_id, :title, CURRENT_TIMESTAMP
                )
                ON CONFLICT (conversation_id, user_id)
                DO UPDATE SET
                    last_time = CURRENT_TIMESTAMP,
                    update_time = CURRENT_TIMESTAMP,
                    deleted = 0
                """,
            ),
            {
                "id": conversation_pk,
                "conversation_id": conversation_id,
                "user_id": user_id,
                "title": title,
            },
        )
        existing_title = await self.session.scalar(
            text(
                """
                SELECT title
                FROM t_conversation
                WHERE conversation_id = :conversation_id
                  AND user_id = :user_id
                  AND deleted = 0
                """,
            ),
            {"conversation_id": conversation_id, "user_id": user_id},
        )
        return str(existing_title or title)

    async def _load_latest_summary_record(self, conversation_id: str, user_id: str) -> SummaryRecord | None:
        result = await self.session.execute(
            text(
                """
                SELECT content, last_message_id
                FROM t_conversation_summary
                WHERE conversation_id = :conversation_id
                  AND user_id = :user_id
                  AND deleted = 0
                ORDER BY update_time DESC, create_time DESC
                LIMIT 1
                """,
            ),
            {"conversation_id": conversation_id, "user_id": user_id},
        )
        row = result.mappings().first()
        if not row:
            return None
        return SummaryRecord(content=str(row["content"]), last_message_id=str(row["last_message_id"]))

    async def _count_messages(self, conversation_id: str, user_id: str) -> int:
        result = await self.session.scalar(
            text(
                """
                SELECT COUNT(*)
                FROM t_message
                WHERE conversation_id = :conversation_id
                  AND user_id = :user_id
                  AND deleted = 0
                """,
            ),
            {"conversation_id": conversation_id, "user_id": user_id},
        )
        return int(result or 0)

    async def _load_messages_for_summary(
        self,
        conversation_id: str,
        user_id: str,
        total_messages: int,
    ) -> list[dict]:
        limit = max(total_messages - self.keep_recent_messages, 0)
        if limit <= 0:
            return []
        result = await self.session.execute(
            text(
                """
                SELECT id, role, content
                FROM (
                    SELECT id, role, content, create_time
                    FROM t_message
                    WHERE conversation_id = :conversation_id
                      AND user_id = :user_id
                      AND deleted = 0
                    ORDER BY create_time DESC, id DESC
                    LIMIT :limit
                ) AS compact_target
                ORDER BY create_time ASC, id ASC
                """,
            ),
            {"conversation_id": conversation_id, "user_id": user_id, "limit": limit},
        )
        return [dict(row) for row in result.mappings().all()]

    async def _summarize_messages(
        self,
        latest_summary: SummaryRecord | None,
        messages: list[dict],
    ) -> str:
        transcript = "\n".join(f"{row['role']}: {row['content']}" for row in messages)
        existing_summary = latest_summary.content if latest_summary else "无"
        if self.llm_service is None:
            return self._fallback_summary(existing_summary, transcript)
        try:
            response = await self.llm_service.complete(
                ChatRequest(
                    messages=[
                        ChatMessage(
                            role="system",
                            content=(
                                "你是 RAG 对话记忆摘要器。请把旧摘要和新增对话压缩为一段中文摘要，"
                                "保留用户目标、关键事实、偏好、约束和未解决问题。"
                            ),
                        ),
                        ChatMessage(
                            role="user",
                            content=f"旧摘要：\n{existing_summary}\n\n新增对话：\n{transcript}",
                        ),
                    ],
                    model=settings.ai_chat_default_model,
                    temperature=0.0,
                    extra_body={"max_tokens": 512},
                ),
            )
            return self._trim_summary(response.content or self._fallback_summary(existing_summary, transcript))
        except Exception:
            return self._fallback_summary(existing_summary, transcript)

    async def _replace_summary(
        self,
        conversation_id: str,
        user_id: str,
        last_message_id: str,
        content: str,
    ) -> None:
        await self.session.execute(
            text(
                """
                UPDATE t_conversation_summary
                SET deleted = 1,
                    update_time = CURRENT_TIMESTAMP
                WHERE conversation_id = :conversation_id
                  AND user_id = :user_id
                  AND deleted = 0
                """,
            ),
            {"conversation_id": conversation_id, "user_id": user_id},
        )
        await self.session.execute(
            text(
                """
                INSERT INTO t_conversation_summary (
                    id, conversation_id, user_id, last_message_id, content
                )
                VALUES (
                    :id, :conversation_id, :user_id, :last_message_id, :content
                )
                """,
            ),
            {
                "id": generate_id(),
                "conversation_id": conversation_id,
                "user_id": user_id,
                "last_message_id": last_message_id,
                "content": self._trim_summary(content),
            },
        )
        await self.session.commit()

    def _fallback_summary(self, existing_summary: str, transcript: str) -> str:
        combined = f"{existing_summary}\n{transcript}" if existing_summary != "无" else transcript
        return self._trim_summary(" ".join(combined.split()))

    def _trim_summary(self, content: str) -> str:
        compact = " ".join(content.strip().split())
        return compact[: self.summary_max_chars]

    @staticmethod
    def _build_title(content: str) -> str:
        compact = " ".join(content.strip().split())
        if not compact:
            return "新对话"
        return compact[:28]
