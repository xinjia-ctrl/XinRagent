import hashlib
import json
from math import ceil
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.ids import generate_id
from app.core.exceptions import RagentException
from app.schemas.document import (
    KnowledgeChunkBatchEnableRequest,
    KnowledgeChunkCreateRequest,
    KnowledgeChunkPageResponse,
    KnowledgeChunkResponse,
    KnowledgeChunkUpdateRequest,
    KnowledgeDocumentChunkLogPageResponse,
    KnowledgeDocumentChunkLogResponse,
    KnowledgeDocumentPageResponse,
    KnowledgeDocumentResponse,
    KnowledgeDocumentSearchItem,
    KnowledgeDocumentUpdateRequest,
)


class DocumentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_documents(
        self,
        kb_id: str,
        current: int = 1,
        size: int = 10,
        status: str | None = None,
        keyword: str | None = None,
    ) -> KnowledgeDocumentPageResponse:
        current = max(current, 1)
        size = max(min(size, 200), 1)
        params: dict[str, object] = {"kb_id": kb_id, "limit": size, "offset": (current - 1) * size}
        where = ["deleted = 0", "kb_id = :kb_id"]
        if status:
            where.append("status = :status")
            params["status"] = status
        if keyword:
            where.append("(doc_name ILIKE :keyword OR source_location ILIKE :keyword)")
            params["keyword"] = f"%{keyword}%"
        where_sql = " AND ".join(where)

        total = await self.session.scalar(
            text(f"SELECT COUNT(*) FROM t_knowledge_document WHERE {where_sql}"),
            params,
        )
        result = await self.session.execute(
            text(
                f"""
                SELECT {self._document_columns()}
                FROM t_knowledge_document
                WHERE {where_sql}
                ORDER BY create_time DESC
                LIMIT :limit OFFSET :offset
                """,
            ),
            params,
        )
        total_count = int(total or 0)
        return KnowledgeDocumentPageResponse(
            records=[self._map_document(row) for row in result.mappings().all()],
            total=total_count,
            size=size,
            current=current,
            pages=ceil(total_count / size) if total_count else 0,
        )

    async def search_documents(self, keyword: str, limit: int = 8) -> list[KnowledgeDocumentSearchItem]:
        limit = max(min(limit, 50), 1)
        result = await self.session.execute(
            text(
                """
                SELECT doc.id, doc.kb_id, doc.doc_name, kb.name AS kb_name
                FROM t_knowledge_document doc
                LEFT JOIN t_knowledge_base kb ON kb.id = doc.kb_id AND kb.deleted = 0
                WHERE doc.deleted = 0
                  AND (:keyword = '' OR doc.doc_name ILIKE :keyword_like)
                ORDER BY doc.create_time DESC
                LIMIT :limit
                """,
            ),
            {"keyword": keyword, "keyword_like": f"%{keyword}%", "limit": limit},
        )
        return [
            KnowledgeDocumentSearchItem(
                id=str(row["id"]),
                kbId=str(row["kb_id"]),
                docName=row["doc_name"],
                kbName=row.get("kb_name"),
            )
            for row in result.mappings().all()
        ]

    async def get_document(self, doc_id: str) -> KnowledgeDocumentResponse:
        return self._map_document(await self._get_document(doc_id))

    async def create_uploaded_document(
        self,
        *,
        kb_id: str,
        doc_id: str,
        doc_name: str,
        file_url: str,
        file_type: str,
        file_size: int,
        user_id: str,
        source_type: str = "file",
        source_location: str | None = None,
        schedule_enabled: bool | int | None = None,
        schedule_cron: str | None = None,
        process_mode: str | None = "chunk",
        chunk_strategy: str | None = None,
        chunk_config: str | dict | None = None,
        pipeline_id: str | None = None,
    ) -> KnowledgeDocumentResponse:
        chunk_config_json = self._to_json_text(chunk_config)
        await self.session.execute(
            text(
                """
                INSERT INTO t_knowledge_document (
                    id, kb_id, doc_name, enabled, chunk_count, file_url, file_type, file_size,
                    process_mode, status, source_type, source_location, schedule_enabled,
                    schedule_cron, chunk_strategy, chunk_config, pipeline_id, created_by, updated_by
                )
                VALUES (
                    :id, :kb_id, :doc_name, 1, 0, :file_url, :file_type, :file_size,
                    :process_mode, 'pending', :source_type, :source_location, :schedule_enabled,
                    :schedule_cron, :chunk_strategy, CAST(:chunk_config AS jsonb), :pipeline_id,
                    :user_id, :user_id
                )
                """,
            ),
            {
                "id": doc_id,
                "kb_id": kb_id,
                "doc_name": doc_name,
                "file_url": file_url,
                "file_type": file_type,
                "file_size": file_size,
                "process_mode": process_mode or "chunk",
                "source_type": source_type,
                "source_location": source_location or file_url,
                "schedule_enabled": self._to_enabled_int(schedule_enabled),
                "schedule_cron": schedule_cron,
                "chunk_strategy": chunk_strategy,
                "chunk_config": chunk_config_json,
                "pipeline_id": pipeline_id,
                "user_id": user_id,
            },
        )
        return KnowledgeDocumentResponse(
            id=doc_id,
            kbId=kb_id,
            docName=doc_name,
            fileUrl=file_url,
            fileType=file_type,
            fileSize=file_size,
            status="pending",
            sourceType=source_type,
            sourceLocation=source_location or file_url,
            scheduleEnabled=self._to_enabled_int(schedule_enabled),
            processMode=process_mode or "chunk",
            chunkStrategy=chunk_strategy,
            chunkConfig=chunk_config_json,
            pipelineId=pipeline_id,
            chunkCount=0,
            createdBy=user_id,
            updatedBy=user_id,
        )

    async def complete_document_ingestion(
        self,
        doc_id: str,
        *,
        status: str,
        chunk_count: int,
        user_id: str,
    ) -> KnowledgeDocumentResponse:
        await self.session.execute(
            text(
                """
                UPDATE t_knowledge_document
                SET status = :status,
                    chunk_count = :chunk_count,
                    updated_by = :user_id,
                    update_time = CURRENT_TIMESTAMP
                WHERE id = :doc_id AND deleted = 0
                """,
            ),
            {"doc_id": doc_id, "status": status, "chunk_count": chunk_count, "user_id": user_id},
        )
        await self.session.commit()
        return await self.get_document(doc_id)

    async def update_document(
        self,
        doc_id: str,
        request: KnowledgeDocumentUpdateRequest,
        user_id: str,
    ) -> KnowledgeDocumentResponse:
        await self._get_document(doc_id)
        values = request.model_dump(exclude_unset=True)
        if not values:
            return await self.get_document(doc_id)

        column_map = {
            "doc_name": "doc_name",
            "process_mode": "process_mode",
            "chunk_strategy": "chunk_strategy",
            "chunk_config": "chunk_config",
            "pipeline_id": "pipeline_id",
            "source_location": "source_location",
            "schedule_enabled": "schedule_enabled",
            "schedule_cron": "schedule_cron",
        }
        params: dict[str, object] = {"doc_id": doc_id, "user_id": user_id}
        assignments: list[str] = []
        for field, column in column_map.items():
            if field not in values:
                continue
            params[field] = self._to_enabled_int(values[field]) if field == "schedule_enabled" else values[field]
            if field == "chunk_config":
                params[field] = self._to_json_text(values[field])
                assignments.append(f"{column} = CAST(:{field} AS jsonb)")
                continue
            assignments.append(f"{column} = :{field}")

        if not assignments:
            return await self.get_document(doc_id)

        assignments.extend(["updated_by = :user_id", "update_time = CURRENT_TIMESTAMP"])
        await self.session.execute(
            text(
                f"""
                UPDATE t_knowledge_document
                SET {", ".join(assignments)}
                WHERE id = :doc_id AND deleted = 0
                """,
            ),
            params,
        )
        await self.session.commit()
        return await self.get_document(doc_id)

    async def start_document_chunk(self, doc_id: str, user_id: str) -> None:
        await self._get_document(doc_id)
        await self.session.execute(
            text(
                """
                UPDATE t_knowledge_document
                SET status = 'pending',
                    updated_by = :user_id,
                    update_time = CURRENT_TIMESTAMP
                WHERE id = :doc_id AND deleted = 0
                """,
            ),
            {"doc_id": doc_id, "user_id": user_id},
        )
        await self.session.commit()

    async def enable_document(self, doc_id: str, value: bool, user_id: str) -> None:
        await self._get_document(doc_id)
        await self.session.execute(
            text(
                """
                UPDATE t_knowledge_document
                SET enabled = :enabled,
                    updated_by = :user_id,
                    update_time = CURRENT_TIMESTAMP
                WHERE id = :doc_id AND deleted = 0
                """,
            ),
            {"doc_id": doc_id, "enabled": 1 if value else 0, "user_id": user_id},
        )
        await self.session.commit()

    async def delete_document(self, doc_id: str, user_id: str) -> None:
        await self._get_document(doc_id)
        await self.session.execute(
            text(
                """
                UPDATE t_knowledge_document
                SET deleted = 1,
                    updated_by = :user_id,
                    update_time = CURRENT_TIMESTAMP
                WHERE id = :doc_id AND deleted = 0
                """,
            ),
            {"doc_id": doc_id, "user_id": user_id},
        )
        await self.session.commit()

    async def list_chunks(
        self,
        doc_id: str,
        current: int = 1,
        size: int = 10,
        enabled: int | None = None,
    ) -> KnowledgeChunkPageResponse:
        current = max(current, 1)
        size = max(min(size, 200), 1)
        params: dict[str, object] = {"doc_id": doc_id, "limit": size, "offset": (current - 1) * size}
        where = ["deleted = 0", "doc_id = :doc_id"]
        if enabled is not None:
            where.append("enabled = :enabled")
            params["enabled"] = enabled
        where_sql = " AND ".join(where)

        total = await self.session.scalar(
            text(f"SELECT COUNT(*) FROM t_knowledge_chunk WHERE {where_sql}"),
            params,
        )
        result = await self.session.execute(
            text(
                f"""
                SELECT {self._chunk_columns()}
                FROM t_knowledge_chunk
                WHERE {where_sql}
                ORDER BY chunk_index ASC
                LIMIT :limit OFFSET :offset
                """,
            ),
            params,
        )
        total_count = int(total or 0)
        return KnowledgeChunkPageResponse(
            records=[self._map_chunk(row) for row in result.mappings().all()],
            total=total_count,
            size=size,
            current=current,
            pages=ceil(total_count / size) if total_count else 0,
        )

    async def create_chunk(
        self,
        doc_id: str,
        request: KnowledgeChunkCreateRequest,
        user_id: str,
    ) -> KnowledgeChunkResponse:
        document = await self._get_document(doc_id)
        chunk_id = request.chunkId or generate_id()
        chunk_index = request.index if request.index is not None else await self._next_chunk_index(doc_id)
        content_hash = hashlib.sha256(request.content.encode("utf-8")).hexdigest()
        await self.session.execute(
            text(
                """
                INSERT INTO t_knowledge_chunk (
                    id, kb_id, doc_id, chunk_index, content, content_hash,
                    char_count, token_count, enabled, created_by, updated_by
                )
                VALUES (
                    :id, :kb_id, :doc_id, :chunk_index, :content, :content_hash,
                    :char_count, :token_count, 1, :user_id, :user_id
                )
                """,
            ),
            {
                "id": chunk_id,
                "kb_id": document["kb_id"],
                "doc_id": doc_id,
                "chunk_index": chunk_index,
                "content": request.content,
                "content_hash": content_hash,
                "char_count": len(request.content),
                "token_count": len(request.content.split()),
                "user_id": user_id,
            },
        )
        await self._refresh_document_chunk_count(doc_id)
        await self.session.commit()
        return await self.get_chunk(doc_id, chunk_id)

    async def get_chunk(self, doc_id: str, chunk_id: str) -> KnowledgeChunkResponse:
        result = await self.session.execute(
            text(
                f"""
                SELECT {self._chunk_columns()}
                FROM t_knowledge_chunk
                WHERE id = :chunk_id AND doc_id = :doc_id AND deleted = 0
                """,
            ),
            {"doc_id": doc_id, "chunk_id": chunk_id},
        )
        row = result.mappings().first()
        if row is None:
            raise RagentException(message="文档分块不存在", code="CHUNK_NOT_FOUND", status_code=404)
        return self._map_chunk(row)

    async def update_chunk(
        self,
        doc_id: str,
        chunk_id: str,
        request: KnowledgeChunkUpdateRequest,
        user_id: str,
    ) -> None:
        await self.get_chunk(doc_id, chunk_id)
        await self.session.execute(
            text(
                """
                UPDATE t_knowledge_chunk
                SET content = :content,
                    content_hash = :content_hash,
                    char_count = :char_count,
                    token_count = :token_count,
                    updated_by = :user_id,
                    update_time = CURRENT_TIMESTAMP
                WHERE id = :chunk_id AND doc_id = :doc_id AND deleted = 0
                """,
            ),
            {
                "doc_id": doc_id,
                "chunk_id": chunk_id,
                "content": request.content,
                "content_hash": hashlib.sha256(request.content.encode("utf-8")).hexdigest(),
                "char_count": len(request.content),
                "token_count": len(request.content.split()),
                "user_id": user_id,
            },
        )
        await self.session.commit()

    async def delete_chunk(self, doc_id: str, chunk_id: str, user_id: str) -> None:
        await self.get_chunk(doc_id, chunk_id)
        await self.session.execute(
            text(
                """
                UPDATE t_knowledge_chunk
                SET deleted = 1,
                    updated_by = :user_id,
                    update_time = CURRENT_TIMESTAMP
                WHERE id = :chunk_id AND doc_id = :doc_id AND deleted = 0
                """,
            ),
            {"doc_id": doc_id, "chunk_id": chunk_id, "user_id": user_id},
        )
        await self._refresh_document_chunk_count(doc_id)
        await self.session.commit()

    async def enable_chunk(self, doc_id: str, chunk_id: str, value: bool, user_id: str) -> None:
        await self.get_chunk(doc_id, chunk_id)
        await self.session.execute(
            text(
                """
                UPDATE t_knowledge_chunk
                SET enabled = :enabled,
                    updated_by = :user_id,
                    update_time = CURRENT_TIMESTAMP
                WHERE id = :chunk_id AND doc_id = :doc_id AND deleted = 0
                """,
            ),
            {"doc_id": doc_id, "chunk_id": chunk_id, "enabled": 1 if value else 0, "user_id": user_id},
        )
        await self.session.commit()

    async def batch_enable_chunks(
        self,
        doc_id: str,
        request: KnowledgeChunkBatchEnableRequest,
        value: bool,
        user_id: str,
    ) -> None:
        chunk_ids = [str(chunk_id) for chunk_id in request.chunkIds]
        if not chunk_ids:
            return
        await self._get_document(doc_id)
        await self.session.execute(
            text(
                """
                UPDATE t_knowledge_chunk
                SET enabled = :enabled,
                    updated_by = :user_id,
                    update_time = CURRENT_TIMESTAMP
                WHERE doc_id = :doc_id AND id = ANY(:chunk_ids) AND deleted = 0
                """,
            ),
            {"doc_id": doc_id, "chunk_ids": chunk_ids, "enabled": 1 if value else 0, "user_id": user_id},
        )
        await self.session.commit()

    async def list_chunk_logs(
        self,
        doc_id: str,
        current: int = 1,
        size: int = 10,
    ) -> KnowledgeDocumentChunkLogPageResponse:
        current = max(current, 1)
        size = max(min(size, 200), 1)
        params: dict[str, object] = {"doc_id": doc_id, "limit": size, "offset": (current - 1) * size}
        total = await self.session.scalar(
            text("SELECT COUNT(*) FROM t_knowledge_document_chunk_log WHERE doc_id = :doc_id"),
            params,
        )
        result = await self.session.execute(
            text(
                """
                SELECT
                    id, doc_id, status, process_mode, chunk_strategy, pipeline_id,
                    NULL AS pipeline_name,
                    extract_duration, chunk_duration, embed_duration, persist_duration,
                    NULL AS other_duration,
                    total_duration, chunk_count, error_message, start_time, end_time, create_time
                FROM t_knowledge_document_chunk_log
                WHERE doc_id = :doc_id
                ORDER BY create_time DESC
                LIMIT :limit OFFSET :offset
                """,
            ),
            params,
        )
        total_count = int(total or 0)
        return KnowledgeDocumentChunkLogPageResponse(
            records=[self._map_chunk_log(row) for row in result.mappings().all()],
            total=total_count,
            size=size,
            current=current,
            pages=ceil(total_count / size) if total_count else 0,
        )

    async def _get_document(self, doc_id: str):
        result = await self.session.execute(
            text(
                f"""
                SELECT {self._document_columns()}
                FROM t_knowledge_document
                WHERE id = :doc_id AND deleted = 0
                """,
            ),
            {"doc_id": doc_id},
        )
        row = result.mappings().first()
        if row is None:
            raise RagentException(message="文档不存在", code="DOCUMENT_NOT_FOUND", status_code=404)
        return row

    async def _next_chunk_index(self, doc_id: str) -> int:
        max_index = await self.session.scalar(
            text(
                """
                SELECT COALESCE(MAX(chunk_index), -1)
                FROM t_knowledge_chunk
                WHERE doc_id = :doc_id AND deleted = 0
                """,
            ),
            {"doc_id": doc_id},
        )
        return int(max_index if max_index is not None else -1) + 1

    async def _refresh_document_chunk_count(self, doc_id: str) -> None:
        await self.session.execute(
            text(
                """
                UPDATE t_knowledge_document
                SET chunk_count = (
                    SELECT COUNT(*) FROM t_knowledge_chunk
                    WHERE doc_id = :doc_id AND deleted = 0
                ),
                update_time = CURRENT_TIMESTAMP
                WHERE id = :doc_id AND deleted = 0
                """,
            ),
            {"doc_id": doc_id},
        )

    @staticmethod
    def _document_columns() -> str:
        return """
            id, kb_id, doc_name, source_type, source_location, schedule_enabled,
            schedule_cron, enabled, chunk_count, file_url, file_type, file_size,
            process_mode, chunk_strategy, chunk_config, pipeline_id, status,
            created_by, updated_by, create_time, update_time
        """

    @staticmethod
    def _chunk_columns() -> str:
        return """
            id, kb_id, doc_id, chunk_index, content, content_hash, char_count,
            token_count, enabled, create_time, update_time
        """

    @staticmethod
    def _map_document(row: Any) -> KnowledgeDocumentResponse:
        return KnowledgeDocumentResponse(
            id=str(row["id"]),
            kbId=str(row["kb_id"]),
            docName=row["doc_name"],
            sourceType=row.get("source_type"),
            sourceLocation=row.get("source_location"),
            scheduleEnabled=row.get("schedule_enabled"),
            scheduleCron=row.get("schedule_cron"),
            enabled=bool(row.get("enabled", 1)),
            chunkCount=int(row.get("chunk_count") or 0),
            fileUrl=row.get("file_url"),
            fileType=row.get("file_type"),
            fileSize=row.get("file_size"),
            processMode=row.get("process_mode"),
            chunkStrategy=row.get("chunk_strategy"),
            chunkConfig=DocumentService._to_json_text(row.get("chunk_config")),
            pipelineId=str(row["pipeline_id"]) if row.get("pipeline_id") is not None else None,
            status=row.get("status"),
            createdBy=str(row["created_by"]) if row.get("created_by") is not None else None,
            updatedBy=str(row["updated_by"]) if row.get("updated_by") is not None else None,
            createTime=row.get("create_time"),
            updateTime=row.get("update_time"),
        )

    @staticmethod
    def _map_chunk(row: Any) -> KnowledgeChunkResponse:
        return KnowledgeChunkResponse(
            id=str(row["id"]),
            kbId=str(row["kb_id"]) if row.get("kb_id") is not None else None,
            docId=str(row["doc_id"]),
            chunkIndex=row.get("chunk_index"),
            content=row.get("content"),
            contentHash=row.get("content_hash"),
            charCount=row.get("char_count"),
            tokenCount=row.get("token_count"),
            enabled=row.get("enabled"),
            createTime=row.get("create_time"),
            updateTime=row.get("update_time"),
        )

    @staticmethod
    def _map_chunk_log(row: Any) -> KnowledgeDocumentChunkLogResponse:
        return KnowledgeDocumentChunkLogResponse(
            id=str(row["id"]),
            docId=str(row["doc_id"]),
            status=row["status"],
            processMode=row.get("process_mode"),
            chunkStrategy=row.get("chunk_strategy"),
            pipelineId=str(row["pipeline_id"]) if row.get("pipeline_id") is not None else None,
            pipelineName=row.get("pipeline_name"),
            extractDuration=row.get("extract_duration"),
            chunkDuration=row.get("chunk_duration"),
            embedDuration=row.get("embed_duration"),
            persistDuration=row.get("persist_duration"),
            otherDuration=row.get("other_duration"),
            totalDuration=row.get("total_duration"),
            chunkCount=row.get("chunk_count"),
            errorMessage=row.get("error_message"),
            startTime=row.get("start_time"),
            endTime=row.get("end_time"),
            createTime=row.get("create_time"),
        )

    @staticmethod
    def _to_json_text(value: str | dict | list | None) -> str | None:
        if value is None or isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def _to_enabled_int(value: bool | int | None) -> int | None:
        if value is None:
            return None
        return 1 if bool(value) else 0
