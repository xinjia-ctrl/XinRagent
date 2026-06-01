from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.ids import generate_id
from app.core.exceptions import RagentException
from app.schemas.conversation import ConversationMessageResponse, ConversationResponse


class ConversationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_conversations(self, user_id: str) -> list[ConversationResponse]:
        result = await self.session.execute(
            text(
                """
                SELECT conversation_id, title, last_time
                FROM t_conversation
                WHERE user_id = :user_id AND deleted = 0
                ORDER BY last_time DESC NULLS LAST, update_time DESC NULLS LAST
                """,
            ),
            {"user_id": user_id},
        )
        return [
            ConversationResponse(
                conversationId=str(row["conversation_id"]),
                title=row["title"] or "新对话",
                lastTime=row["last_time"],
            )
            for row in result.mappings()
        ]

    async def rename_conversation(self, conversation_id: str, user_id: str, title: str) -> None:
        result = await self.session.execute(
            text(
                """
                UPDATE t_conversation
                SET title = :title, update_time = CURRENT_TIMESTAMP
                WHERE conversation_id = :conversation_id AND user_id = :user_id AND deleted = 0
                """,
            ),
            {"conversation_id": conversation_id, "user_id": user_id, "title": title.strip()},
        )
        if result.rowcount == 0:
            raise RagentException(message="会话不存在", code="CONVERSATION_NOT_FOUND", status_code=404)
        await self.session.commit()

    async def delete_conversation(self, conversation_id: str, user_id: str) -> None:
        result = await self.session.execute(
            text(
                """
                UPDATE t_conversation
                SET deleted = 1, update_time = CURRENT_TIMESTAMP
                WHERE conversation_id = :conversation_id AND user_id = :user_id AND deleted = 0
                """,
            ),
            {"conversation_id": conversation_id, "user_id": user_id},
        )
        if result.rowcount == 0:
            raise RagentException(message="会话不存在", code="CONVERSATION_NOT_FOUND", status_code=404)
        await self.session.commit()

    async def list_messages(self, conversation_id: str, user_id: str) -> list[ConversationMessageResponse]:
        result = await self.session.execute(
            text(
                """
                SELECT
                    m.id,
                    m.conversation_id,
                    m.role,
                    m.content,
                    m.thinking_content,
                    m.thinking_duration,
                    m.create_time,
                    (
                        SELECT f.vote
                        FROM t_message_feedback f
                        WHERE f.message_id = m.id AND f.user_id = :user_id AND f.deleted = 0
                        ORDER BY f.update_time DESC NULLS LAST, f.create_time DESC NULLS LAST
                        LIMIT 1
                    ) AS vote
                FROM t_message m
                WHERE m.conversation_id = :conversation_id
                  AND m.user_id = :user_id
                  AND m.deleted = 0
                ORDER BY m.create_time ASC NULLS LAST
                """,
            ),
            {"conversation_id": conversation_id, "user_id": user_id},
        )
        return [
            ConversationMessageResponse(
                id=str(row["id"]),
                conversationId=str(row["conversation_id"]),
                role=row["role"],
                content=row["content"],
                thinkingContent=row["thinking_content"],
                thinkingDuration=row["thinking_duration"],
                vote=row["vote"],
                createTime=row["create_time"],
            )
            for row in result.mappings()
        ]

    async def save_message_feedback(self, message_id: str, user_id: str, vote: int) -> None:
        message = await self.session.execute(
            text(
                """
                SELECT conversation_id
                FROM t_message
                WHERE id = :message_id AND user_id = :user_id AND deleted = 0
                """,
            ),
            {"message_id": message_id, "user_id": user_id},
        )
        row = message.mappings().first()
        if row is None:
            raise RagentException(message="消息不存在", code="MESSAGE_NOT_FOUND", status_code=404)

        if vote == 0:
            await self.session.execute(
                text(
                    """
                    UPDATE t_message_feedback
                    SET deleted = 1, update_time = CURRENT_TIMESTAMP
                    WHERE message_id = :message_id AND user_id = :user_id AND deleted = 0
                    """,
                ),
                {"message_id": message_id, "user_id": user_id},
            )
        else:
            await self.session.execute(
                text(
                    """
                    INSERT INTO t_message_feedback (
                        id, message_id, conversation_id, user_id, vote, create_time, update_time, deleted
                    )
                    VALUES (
                        :id, :message_id, :conversation_id, :user_id, :vote,
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 0
                    )
                    """,
                ),
                {
                    "id": generate_id(),
                    "message_id": message_id,
                    "conversation_id": row["conversation_id"],
                    "user_id": user_id,
                    "vote": vote,
                },
            )
        await self.session.commit()
