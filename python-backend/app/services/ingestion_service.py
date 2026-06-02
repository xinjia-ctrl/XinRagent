import json
from math import ceil
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.ids import generate_id
from app.core.exceptions import RagentException
from app.schemas.ingestion import (
    IngestionPipelineNodePayload,
    IngestionPipelineNodeResponse,
    IngestionPipelinePageResponse,
    IngestionPipelinePayload,
    IngestionPipelineResponse,
    IngestionResultResponse,
    IngestionTaskCreateRequest,
    IngestionTaskNodeLog,
    IngestionTaskNodeResponse,
    IngestionTaskPageResponse,
    IngestionTaskResponse,
)


class IngestionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_pipelines(
        self,
        page_no: int = 1,
        page_size: int = 10,
        keyword: str | None = None,
    ) -> IngestionPipelinePageResponse:
        page_no = max(page_no, 1)
        page_size = max(min(page_size, 200), 1)
        params: dict[str, object] = {"limit": page_size, "offset": (page_no - 1) * page_size}
        where = ["deleted = 0"]
        if keyword:
            where.append("(name ILIKE :keyword OR description ILIKE :keyword)")
            params["keyword"] = f"%{keyword}%"
        where_sql = " AND ".join(where)

        total = await self.session.scalar(
            text(f"SELECT COUNT(*) FROM t_ingestion_pipeline WHERE {where_sql}"),
            params,
        )
        result = await self.session.execute(
            text(
                f"""
                SELECT id, name, description, created_by, create_time, update_time
                FROM t_ingestion_pipeline
                WHERE {where_sql}
                ORDER BY create_time DESC
                LIMIT :limit OFFSET :offset
                """,
            ),
            params,
        )
        pipelines = [self._map_pipeline(row, nodes=[]) for row in result.mappings().all()]
        total_count = int(total or 0)
        return IngestionPipelinePageResponse(
            records=pipelines,
            total=total_count,
            size=page_size,
            current=page_no,
            pages=ceil(total_count / page_size) if total_count else 0,
        )

    async def get_pipeline(self, pipeline_id: str) -> IngestionPipelineResponse:
        pipeline = await self._get_pipeline_row(pipeline_id)
        return self._map_pipeline(pipeline, nodes=await self._list_pipeline_nodes(pipeline_id))

    async def create_pipeline(
        self,
        request: IngestionPipelinePayload,
        user_id: str,
    ) -> IngestionPipelineResponse:
        pipeline_id = generate_id()
        await self.session.execute(
            text(
                """
                INSERT INTO t_ingestion_pipeline (id, name, description, created_by, updated_by)
                VALUES (:id, :name, :description, :user_id, :user_id)
                """,
            ),
            {
                "id": pipeline_id,
                "name": request.name,
                "description": request.description,
                "user_id": user_id,
            },
        )
        await self._insert_pipeline_nodes(pipeline_id, request.nodes or [], user_id)
        await self.session.commit()
        return await self.get_pipeline(pipeline_id)

    async def update_pipeline(
        self,
        pipeline_id: str,
        request: IngestionPipelinePayload,
        user_id: str,
    ) -> IngestionPipelineResponse:
        await self._get_pipeline_row(pipeline_id)
        await self.session.execute(
            text(
                """
                UPDATE t_ingestion_pipeline
                SET name = :name,
                    description = :description,
                    updated_by = :user_id,
                    update_time = CURRENT_TIMESTAMP
                WHERE id = :id AND deleted = 0
                """,
            ),
            {
                "id": pipeline_id,
                "name": request.name,
                "description": request.description,
                "user_id": user_id,
            },
        )
        if request.nodes is not None:
            await self.session.execute(
                text(
                    """
                    UPDATE t_ingestion_pipeline_node
                    SET deleted = 1, updated_by = :user_id, update_time = CURRENT_TIMESTAMP
                    WHERE pipeline_id = :pipeline_id AND deleted = 0
                    """,
                ),
                {"pipeline_id": pipeline_id, "user_id": user_id},
            )
            await self._insert_pipeline_nodes(pipeline_id, request.nodes, user_id)
        await self.session.commit()
        return await self.get_pipeline(pipeline_id)

    async def delete_pipeline(self, pipeline_id: str, user_id: str) -> None:
        await self._get_pipeline_row(pipeline_id)
        await self.session.execute(
            text(
                """
                UPDATE t_ingestion_pipeline
                SET deleted = 1,
                    updated_by = :user_id,
                    update_time = CURRENT_TIMESTAMP
                WHERE id = :id AND deleted = 0
                """,
            ),
            {"id": pipeline_id, "user_id": user_id},
        )
        await self.session.execute(
            text(
                """
                UPDATE t_ingestion_pipeline_node
                SET deleted = 1,
                    updated_by = :user_id,
                    update_time = CURRENT_TIMESTAMP
                WHERE pipeline_id = :pipeline_id AND deleted = 0
                """,
            ),
            {"pipeline_id": pipeline_id, "user_id": user_id},
        )
        await self.session.commit()

    async def list_tasks(
        self,
        page_no: int = 1,
        page_size: int = 10,
        status: str | None = None,
    ) -> IngestionTaskPageResponse:
        page_no = max(page_no, 1)
        page_size = max(min(page_size, 200), 1)
        params: dict[str, object] = {"limit": page_size, "offset": (page_no - 1) * page_size}
        where = ["deleted = 0"]
        if status:
            where.append("status = :status")
            params["status"] = status
        where_sql = " AND ".join(where)

        total = await self.session.scalar(
            text(f"SELECT COUNT(*) FROM t_ingestion_task WHERE {where_sql}"),
            params,
        )
        result = await self.session.execute(
            text(
                f"""
                SELECT {self._task_columns()}
                FROM t_ingestion_task
                WHERE {where_sql}
                ORDER BY create_time DESC
                LIMIT :limit OFFSET :offset
                """,
            ),
            params,
        )
        total_count = int(total or 0)
        return IngestionTaskPageResponse(
            records=[self._map_task(row) for row in result.mappings().all()],
            total=total_count,
            size=page_size,
            current=page_no,
            pages=ceil(total_count / page_size) if total_count else 0,
        )

    async def get_task(self, task_id: str) -> IngestionTaskResponse:
        return self._map_task(await self._get_task_row(task_id))

    async def list_task_nodes(self, task_id: str) -> list[IngestionTaskNodeResponse]:
        await self._get_task_row(task_id)
        result = await self.session.execute(
            text(
                """
                SELECT
                    id, task_id, pipeline_id, node_id, node_type, node_order, status,
                    duration_ms, message, error_message, output_json, create_time, update_time
                FROM t_ingestion_task_node
                WHERE task_id = :task_id AND deleted = 0
                ORDER BY node_order ASC, create_time ASC
                """,
            ),
            {"task_id": task_id},
        )
        return [self._map_task_node(row) for row in result.mappings().all()]

    async def create_task(
        self,
        request: IngestionTaskCreateRequest,
        user_id: str,
    ) -> IngestionResultResponse:
        await self._get_pipeline_row(request.pipeline_id)
        task_id = generate_id()
        metadata = dict(request.metadata or {})
        if request.vectorSpaceId is not None:
            metadata["vectorSpaceId"] = request.vectorSpaceId
        await self._insert_task(
            task_id=task_id,
            pipeline_id=request.pipeline_id,
            source_type=request.source.type,
            source_location=request.source.location,
            source_file_name=request.source.fileName,
            metadata=metadata or None,
            user_id=user_id,
        )
        await self._create_task_nodes_from_pipeline(task_id, request.pipeline_id)
        await self.session.commit()
        return IngestionResultResponse(
            taskId=task_id,
            pipelineId=request.pipeline_id,
            status="pending",
            chunkCount=0,
            message="任务已创建",
        )

    async def create_upload_task(
        self,
        *,
        pipeline_id: str,
        source_location: str,
        source_file_name: str,
        user_id: str,
    ) -> IngestionResultResponse:
        await self._get_pipeline_row(pipeline_id)
        task_id = generate_id()
        await self._insert_task(
            task_id=task_id,
            pipeline_id=pipeline_id,
            source_type="file",
            source_location=source_location,
            source_file_name=source_file_name,
            metadata=None,
            user_id=user_id,
        )
        await self._create_task_nodes_from_pipeline(task_id, pipeline_id)
        await self.session.commit()
        return IngestionResultResponse(
            taskId=task_id,
            pipelineId=pipeline_id,
            status="pending",
            chunkCount=0,
            message="文件任务已创建",
        )

    async def _get_pipeline_row(self, pipeline_id: str):
        result = await self.session.execute(
            text(
                """
                SELECT id, name, description, created_by, create_time, update_time
                FROM t_ingestion_pipeline
                WHERE id = :id AND deleted = 0
                """,
            ),
            {"id": pipeline_id},
        )
        row = result.mappings().first()
        if row is None:
            raise RagentException(message="入库流水线不存在", code="INGESTION_PIPELINE_NOT_FOUND", status_code=404)
        return row

    async def _get_task_row(self, task_id: str):
        result = await self.session.execute(
            text(
                f"""
                SELECT {self._task_columns()}
                FROM t_ingestion_task
                WHERE id = :id AND deleted = 0
                """,
            ),
            {"id": task_id},
        )
        row = result.mappings().first()
        if row is None:
            raise RagentException(message="入库任务不存在", code="INGESTION_TASK_NOT_FOUND", status_code=404)
        return row

    async def _list_pipeline_nodes(self, pipeline_id: str) -> list[IngestionPipelineNodeResponse]:
        result = await self.session.execute(
            text(
                """
                SELECT id, node_id, node_type, settings_json, condition_json, next_node_id
                FROM t_ingestion_pipeline_node
                WHERE pipeline_id = :pipeline_id AND deleted = 0
                ORDER BY create_time ASC
                """,
            ),
            {"pipeline_id": pipeline_id},
        )
        return [self._map_pipeline_node(row) for row in result.mappings().all()]

    async def _insert_pipeline_nodes(
        self,
        pipeline_id: str,
        nodes: list[IngestionPipelineNodePayload],
        user_id: str,
    ) -> None:
        for node in nodes:
            await self.session.execute(
                text(
                    """
                    INSERT INTO t_ingestion_pipeline_node (
                        id, pipeline_id, node_id, node_type, next_node_id,
                        settings_json, condition_json, created_by, updated_by
                    )
                    VALUES (
                        :id, :pipeline_id, :node_id, :node_type, :next_node_id,
                        CAST(:settings_json AS jsonb), CAST(:condition_json AS jsonb),
                        :user_id, :user_id
                    )
                    """,
                ),
                {
                    "id": generate_id(),
                    "pipeline_id": pipeline_id,
                    "node_id": node.node_id,
                    "node_type": node.node_type,
                    "next_node_id": node.next_node_id,
                    "settings_json": self._to_json_text(node.settings),
                    "condition_json": self._to_json_text(node.condition),
                    "user_id": user_id,
                },
            )

    async def _insert_task(
        self,
        *,
        task_id: str,
        pipeline_id: str,
        source_type: str,
        source_location: str | None,
        source_file_name: str | None,
        metadata: dict[str, Any] | None,
        user_id: str,
    ) -> None:
        await self.session.execute(
            text(
                """
                INSERT INTO t_ingestion_task (
                    id, pipeline_id, source_type, source_location, source_file_name,
                    status, chunk_count, logs_json, metadata_json, started_at,
                    created_by, updated_by
                )
                VALUES (
                    :id, :pipeline_id, :source_type, :source_location, :source_file_name,
                    'pending', 0, CAST(:logs_json AS jsonb), CAST(:metadata_json AS jsonb),
                    CURRENT_TIMESTAMP, :user_id, :user_id
                )
                """,
            ),
            {
                "id": task_id,
                "pipeline_id": pipeline_id,
                "source_type": source_type,
                "source_location": source_location,
                "source_file_name": source_file_name,
                "logs_json": self._to_json_text([]),
                "metadata_json": self._to_json_text(metadata),
                "user_id": user_id,
            },
        )

    async def _create_task_nodes_from_pipeline(self, task_id: str, pipeline_id: str) -> None:
        result = await self.session.execute(
            text(
                """
                SELECT node_id, node_type
                FROM t_ingestion_pipeline_node
                WHERE pipeline_id = :pipeline_id AND deleted = 0
                ORDER BY create_time ASC
                """,
            ),
            {"pipeline_id": pipeline_id},
        )
        for index, row in enumerate(result.mappings().all()):
            await self.session.execute(
                text(
                    """
                    INSERT INTO t_ingestion_task_node (
                        id, task_id, pipeline_id, node_id, node_type, node_order, status
                    )
                    VALUES (
                        :id, :task_id, :pipeline_id, :node_id, :node_type, :node_order, 'pending'
                    )
                    """,
                ),
                {
                    "id": generate_id(),
                    "task_id": task_id,
                    "pipeline_id": pipeline_id,
                    "node_id": row["node_id"],
                    "node_type": row["node_type"],
                    "node_order": index,
                },
            )

    @staticmethod
    def _map_pipeline(row: Any, nodes: list[IngestionPipelineNodeResponse]) -> IngestionPipelineResponse:
        return IngestionPipelineResponse(
            id=str(row["id"]),
            name=row["name"],
            description=row.get("description"),
            createdBy=str(row["created_by"]) if row.get("created_by") is not None else None,
            nodes=nodes,
            createTime=row.get("create_time"),
            updateTime=row.get("update_time"),
        )

    @staticmethod
    def _map_pipeline_node(row: Any) -> IngestionPipelineNodeResponse:
        return IngestionPipelineNodeResponse(
            id=str(row["id"]),
            nodeId=row["node_id"],
            nodeType=row["node_type"],
            settings=IngestionService._to_dict(row.get("settings_json")),
            condition=IngestionService._to_dict(row.get("condition_json")),
            nextNodeId=row.get("next_node_id"),
        )

    @staticmethod
    def _map_task(row: Any) -> IngestionTaskResponse:
        return IngestionTaskResponse(
            id=str(row["id"]),
            pipelineId=str(row["pipeline_id"]),
            sourceType=row.get("source_type"),
            sourceLocation=row.get("source_location"),
            sourceFileName=row.get("source_file_name"),
            status=row.get("status"),
            chunkCount=row.get("chunk_count"),
            errorMessage=row.get("error_message"),
            logs=IngestionService._to_task_logs(row.get("logs_json")),
            metadata=IngestionService._to_dict(row.get("metadata_json")),
            startedAt=row.get("started_at"),
            completedAt=row.get("completed_at"),
            createdBy=str(row["created_by"]) if row.get("created_by") is not None else None,
            createTime=row.get("create_time"),
            updateTime=row.get("update_time"),
        )

    @staticmethod
    def _map_task_node(row: Any) -> IngestionTaskNodeResponse:
        return IngestionTaskNodeResponse(
            id=str(row["id"]),
            taskId=str(row["task_id"]),
            pipelineId=str(row["pipeline_id"]),
            nodeId=row["node_id"],
            nodeType=row["node_type"],
            nodeOrder=row.get("node_order"),
            status=row.get("status"),
            durationMs=row.get("duration_ms"),
            message=row.get("message"),
            errorMessage=row.get("error_message"),
            output=IngestionService._to_dict(row.get("output_json")),
            createTime=row.get("create_time"),
            updateTime=row.get("update_time"),
        )

    @staticmethod
    def _task_columns() -> str:
        return """
            id, pipeline_id, source_type, source_location, source_file_name,
            status, chunk_count, error_message, logs_json, metadata_json,
            started_at, completed_at, created_by, create_time, update_time
        """

    @staticmethod
    def _to_json_text(value: Any) -> str | None:
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def _to_dict(value: Any) -> dict[str, Any] | None:
        if value is None or isinstance(value, dict):
            return value
        if isinstance(value, str):
            return json.loads(value)
        return dict(value)

    @staticmethod
    def _to_task_logs(value: Any) -> list[IngestionTaskNodeLog] | None:
        if value is None:
            return None
        logs = json.loads(value) if isinstance(value, str) else value
        return [IngestionTaskNodeLog(**item) for item in logs]
