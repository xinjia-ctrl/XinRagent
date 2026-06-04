from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.ids import generate_id
from app.infra_ai.chat import ChatMessage


@dataclass(frozen=True)
class AppendedMessage:
    message_id: str
    title: str | None = None


class ConversationMemoryService:
    def __init__(self, session: AsyncSession, history_limit: int = 10) -> None:
        self.session = session
        self.history_limit = history_limit

    async def load_history(self, conversation_id: str | None, user_id: str | None) -> list[ChatMessage]:
        if not conversation_id or not user_id:
            return []

        summary = await self._load_latest_summary(conversation_id, user_id)
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
            messages.insert(0, ChatMessage(role="system", content=f"以下是此前对话摘要：{summary}"))
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

    async def _load_latest_summary(self, conversation_id: str, user_id: str) -> str | None:
        result = await self.session.scalar(
            text(
                """
                SELECT content
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
        return str(result) if result else None

    @staticmethod
    def _build_title(content: str) -> str:
        compact = " ".join(content.strip().split())
        if not compact:
            return "新对话"
        return compact[:28]
