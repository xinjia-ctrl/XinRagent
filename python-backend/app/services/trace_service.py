from math import ceil
from time import perf_counter

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.ids import generate_id
from app.core.exceptions import RagentException
from app.schemas.trace import TraceDetailResponse, TraceNodeResponse, TraceRunPageResponse, TraceRunResponse


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

    async def list_runs(
        self,
        current: int = 1,
        size: int = 10,
        trace_id: str | None = None,
        conversation_id: str | None = None,
        task_id: str | None = None,
        status: str | None = None,
    ) -> TraceRunPageResponse:
        current = max(current, 1)
        size = max(min(size, 200), 1)
        params: dict[str, object] = {"limit": size, "offset": (current - 1) * size}
        where = ["run.deleted = 0"]
        if trace_id:
            where.append("run.trace_id = :trace_id")
            params["trace_id"] = trace_id
        if conversation_id:
            where.append("run.conversation_id = :conversation_id")
            params["conversation_id"] = conversation_id
        if task_id:
            where.append("run.task_id = :task_id")
            params["task_id"] = task_id
        if status:
            where.append("run.status = :status")
            params["status"] = status
        where_sql = " AND ".join(where)

        total = await self.session.scalar(
            text(f"SELECT COUNT(*) FROM t_rag_trace_run run WHERE {where_sql}"),
            params,
        )
        result = await self.session.execute(
            text(
                f"""
                SELECT {self._run_columns()}
                FROM t_rag_trace_run run
                LEFT JOIN t_user usr ON usr.id = run.user_id
                WHERE {where_sql}
                ORDER BY run.create_time DESC
                LIMIT :limit
                OFFSET :offset
                """,
            ),
            params,
        )
        total_count = int(total or 0)
        return TraceRunPageResponse(
            records=[self._map_run(row) for row in result.mappings().all()],
            total=total_count,
            size=size,
            current=current,
            pages=ceil(total_count / size) if total_count else 0,
        )

    async def get_run_detail(self, trace_id: str) -> TraceDetailResponse:
        run_result = await self.session.execute(
            text(
                """
                SELECT
                    run.trace_id, run.trace_name, run.entry_method, run.conversation_id,
                    run.task_id, run.user_id, usr.username AS user_name, run.status,
                    run.error_message, run.duration_ms, run.start_time, run.end_time
                FROM t_rag_trace_run run
                LEFT JOIN t_user usr ON usr.id = run.user_id
                WHERE run.trace_id = :trace_id AND run.deleted = 0
                """,
            ),
            {"trace_id": trace_id},
        )
        run = run_result.mappings().first()
        if run is None:
            raise RagentException(message="Trace 不存在", code="TRACE_NOT_FOUND", status_code=404)
        return TraceDetailResponse(
            run=self._map_run(run),
            nodes=await self.list_nodes(trace_id),
        )

    async def list_nodes(self, trace_id: str) -> list[TraceNodeResponse]:
        node_result = await self.session.execute(
            text(
                """
                SELECT
                    trace_id, node_id, parent_node_id, depth, node_type, node_name,
                    class_name, method_name, status, error_message, duration_ms,
                    start_time, end_time
                FROM t_rag_trace_node
                WHERE trace_id = :trace_id AND deleted = 0
                ORDER BY create_time ASC
                """,
            ),
            {"trace_id": trace_id},
        )
        return [self._map_node(row) for row in node_result.mappings().all()]

    @staticmethod
    def elapsed_ms(started_at: float) -> int:
        return int((perf_counter() - started_at) * 1000)

    @staticmethod
    def _map_run(row) -> TraceRunResponse:
        return TraceRunResponse(
            traceId=str(row["trace_id"]),
            traceName=row["trace_name"],
            entryMethod=row.get("entry_method"),
            conversationId=str(row["conversation_id"]) if row["conversation_id"] is not None else None,
            taskId=str(row["task_id"]) if row["task_id"] is not None else None,
            userName=row.get("user_name"),
            username=row.get("user_name"),
            userId=str(row["user_id"]) if row["user_id"] is not None else None,
            status=row["status"],
            errorMessage=row["error_message"],
            durationMs=row["duration_ms"],
            startTime=row.get("start_time"),
            endTime=row.get("end_time"),
        )

    @staticmethod
    def _map_node(row) -> TraceNodeResponse:
        return TraceNodeResponse(
            traceId=str(row["trace_id"]) if row.get("trace_id") is not None else None,
            nodeId=str(row["node_id"]),
            parentNodeId=str(row["parent_node_id"]) if row.get("parent_node_id") is not None else None,
            depth=row.get("depth"),
            nodeName=row["node_name"],
            nodeType=row["node_type"],
            className=row.get("class_name"),
            methodName=row.get("method_name"),
            status=row["status"],
            durationMs=row["duration_ms"],
            errorMessage=row["error_message"],
            startTime=row.get("start_time"),
            endTime=row.get("end_time"),
        )

    @staticmethod
    def _run_columns() -> str:
        return """
            run.trace_id, run.trace_name, run.entry_method, run.conversation_id,
            run.task_id, run.user_id, usr.username AS user_name, run.status,
            run.error_message, run.duration_ms, run.start_time, run.end_time
        """
