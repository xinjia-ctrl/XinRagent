from time import perf_counter

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.ids import generate_id
from app.core.exceptions import RagentException
from app.schemas.trace import TraceDetailResponse, TraceNodeResponse, TraceRunResponse


class TraceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def start_run(
        self,
        trace_name: str,
        task_id: str,
        user_id: str | None,
        conversation_id: str | None,
        entry_method: str = "rag.chat",
    ) -> str:
        trace_id = generate_id()
        await self.session.execute(
            text(
                """
                INSERT INTO t_rag_trace_run (
                    id, trace_id, trace_name, entry_method, conversation_id,
                    task_id, user_id, status, start_time
                )
                VALUES (
                    :id, :trace_id, :trace_name, :entry_method, :conversation_id,
                    :task_id, :user_id, 'RUNNING', CURRENT_TIMESTAMP
                )
                """,
            ),
            {
                "id": trace_id,
                "trace_id": trace_id,
                "trace_name": trace_name,
                "entry_method": entry_method,
                "conversation_id": conversation_id,
                "task_id": task_id,
                "user_id": user_id,
            },
        )
        await self.session.commit()
        return trace_id

    async def finish_run(self, trace_id: str, status: str = "SUCCESS", error_message: str | None = None) -> None:
        await self.session.execute(
            text(
                """
                UPDATE t_rag_trace_run
                SET status = :status,
                    error_message = :error_message,
                    end_time = CURRENT_TIMESTAMP,
                    duration_ms = EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - start_time)) * 1000,
                    update_time = CURRENT_TIMESTAMP
                WHERE trace_id = :trace_id
                """,
            ),
            {"trace_id": trace_id, "status": status, "error_message": error_message},
        )
        await self.session.commit()

    async def record_node(
        self,
        trace_id: str,
        node_name: str,
        node_type: str,
        status: str,
        duration_ms: int,
        error_message: str | None = None,
    ) -> None:
        node_id = generate_id()
        await self.session.execute(
            text(
                """
                INSERT INTO t_rag_trace_node (
                    id, trace_id, node_id, depth, node_type, node_name,
                    status, error_message, start_time, end_time, duration_ms
                )
                VALUES (
                    :id, :trace_id, :node_id, 0, :node_type, :node_name,
                    :status, :error_message, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, :duration_ms
                )
                """,
            ),
            {
                "id": node_id,
                "trace_id": trace_id,
                "node_id": node_id,
                "node_type": node_type,
                "node_name": node_name,
                "status": status,
                "error_message": error_message,
                "duration_ms": duration_ms,
            },
        )
        await self.session.commit()

    async def list_runs(self, limit: int = 50) -> list[TraceRunResponse]:
        result = await self.session.execute(
            text(
                """
                SELECT trace_id, trace_name, conversation_id, task_id, user_id,
                       status, error_message, duration_ms
                FROM t_rag_trace_run
                WHERE deleted = 0
                ORDER BY create_time DESC
                LIMIT :limit
                """,
            ),
            {"limit": limit},
        )
        return [self._map_run(row) for row in result.mappings().all()]

    async def get_run_detail(self, trace_id: str) -> TraceDetailResponse:
        run_result = await self.session.execute(
            text(
                """
                SELECT trace_id, trace_name, conversation_id, task_id, user_id,
                       status, error_message, duration_ms
                FROM t_rag_trace_run
                WHERE trace_id = :trace_id AND deleted = 0
                """,
            ),
            {"trace_id": trace_id},
        )
        run = run_result.mappings().first()
        if run is None:
            raise RagentException(message="Trace 不存在", code="TRACE_NOT_FOUND", status_code=404)

        node_result = await self.session.execute(
            text(
                """
                SELECT node_id, node_name, node_type, status, duration_ms, error_message
                FROM t_rag_trace_node
                WHERE trace_id = :trace_id AND deleted = 0
                ORDER BY create_time ASC
                """,
            ),
            {"trace_id": trace_id},
        )
        return TraceDetailResponse(
            run=self._map_run(run),
            nodes=[self._map_node(row) for row in node_result.mappings().all()],
        )

    @staticmethod
    def elapsed_ms(started_at: float) -> int:
        return int((perf_counter() - started_at) * 1000)

    @staticmethod
    def _map_run(row) -> TraceRunResponse:
        return TraceRunResponse(
            trace_id=str(row["trace_id"]),
            trace_name=row["trace_name"],
            conversation_id=str(row["conversation_id"]) if row["conversation_id"] is not None else None,
            task_id=str(row["task_id"]) if row["task_id"] is not None else None,
            user_id=str(row["user_id"]) if row["user_id"] is not None else None,
            status=row["status"],
            error_message=row["error_message"],
            duration_ms=row["duration_ms"],
        )

    @staticmethod
    def _map_node(row) -> TraceNodeResponse:
        return TraceNodeResponse(
            node_id=str(row["node_id"]),
            node_name=row["node_name"],
            node_type=row["node_type"],
            status=row["status"],
            duration_ms=row["duration_ms"],
            error_message=row["error_message"],
        )
