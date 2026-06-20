from dataclasses import dataclass, field
import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.ids import generate_id
from app.core.context import get_request_context
from app.infra.task_queue import TaskQueue


@dataclass(frozen=True)
class OutboxMessage:
    id: str
    topic: str
    event_name: str
    payload: dict[str, Any] = field(default_factory=dict)
    idempotency_key: str | None = None
    context: dict[str, Any] = field(default_factory=dict)


class TransactionalTaskPublisher:
    def __init__(self, session: AsyncSession, task_queue: TaskQueue) -> None:
        self.session = session
        self.task_queue = task_queue

    async def stage(
        self,
        event_name: str,
        payload: dict[str, Any],
        *,
        topic: str = "default",
        idempotency_key: str | None = None,
    ) -> OutboxMessage:
        message = OutboxMessage(
            id=generate_id(),
            topic=topic,
            event_name=event_name,
            payload=payload,
            idempotency_key=idempotency_key,
            context=_current_context_payload(),
        )
        await self.session.execute(
            text(
                """
                INSERT INTO t_task_outbox (
                    id, topic, event_name, payload_json, idempotency_key, context_json, status
                )
                VALUES (
                    :id, :topic, :event_name, CAST(:payload_json AS jsonb),
                    :idempotency_key, CAST(:context_json AS jsonb), 'PENDING'
                )
                """,
            ),
            {
                "id": message.id,
                "topic": message.topic,
                "event_name": message.event_name,
                "payload_json": json.dumps(message.payload, ensure_ascii=False),
                "idempotency_key": message.idempotency_key,
                "context_json": json.dumps(message.context, ensure_ascii=False),
            },
        )
        return message

    async def dispatch_pending(self, limit: int = 100) -> int:
        result = await self.session.execute(
            text(
                """
                SELECT id, event_name, payload_json, idempotency_key
                FROM t_task_outbox
                WHERE status IN ('PENDING', 'FAILED')
                  AND deleted = 0
                  AND (next_retry_at IS NULL OR next_retry_at <= CURRENT_TIMESTAMP)
                ORDER BY create_time ASC
                LIMIT :limit
                FOR UPDATE SKIP LOCKED
                """,
            ),
            {"limit": limit},
        )
        dispatched = 0
        for row in result.mappings().all():
            try:
                await self.task_queue.enqueue(
                    str(row["event_name"]),
                    _loads_json(row["payload_json"]),
                    task_id=str(row["id"]),
                    idempotency_key=row.get("idempotency_key"),
                )
                await self._mark_sent(str(row["id"]))
                dispatched += 1
            except Exception as exc:
                await self._mark_failed(str(row["id"]), str(exc))
        await self.session.commit()
        return dispatched

    async def _mark_sent(self, message_id: str) -> None:
        await self.session.execute(
            text(
                """
                UPDATE t_task_outbox
                SET status = 'SENT',
                    sent_at = CURRENT_TIMESTAMP,
                    update_time = CURRENT_TIMESTAMP
                WHERE id = :id
                """,
            ),
            {"id": message_id},
        )

    async def _mark_failed(self, message_id: str, error: str) -> None:
        await self.session.execute(
            text(
                """
                UPDATE t_task_outbox
                SET status = 'FAILED',
                    attempts = attempts + 1,
                    last_error = :error,
                    next_retry_at = CURRENT_TIMESTAMP + INTERVAL '30 seconds',
                    update_time = CURRENT_TIMESTAMP
                WHERE id = :id
                """,
            ),
            {"id": message_id, "error": error[:2000]},
        )


def _current_context_payload() -> dict[str, Any]:
    context = get_request_context()
    if context is None:
        return {}
    return {
        "requestId": context.request_id,
        "userId": context.user_id,
        "expiresAt": context.expires_at,
    }


def _loads_json(value: object) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    return json.loads(str(value))
