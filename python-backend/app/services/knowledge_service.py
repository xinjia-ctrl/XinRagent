from math import ceil

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.ids import generate_id
from app.core.config import settings
from app.core.exceptions import RagentException
from app.schemas.knowledge import (
    ChunkStrategyOption,
    DeleteResponse,
    KnowledgeBaseCreateRequest,
    KnowledgeBasePageResponse,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdateRequest,
)


class KnowledgeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_knowledge_bases(
        self,
        current: int = 1,
        size: int = 10,
        name: str | None = None,
    ) -> KnowledgeBasePageResponse:
        current = max(current, 1)
        size = max(min(size, 200), 1)
        params: dict[str, object] = {"limit": size, "offset": (current - 1) * size}
        where = ["kb.deleted = 0"]
        if name:
            where.append("kb.name ILIKE :name")
            params["name"] = f"%{name}%"
        where_sql = " AND ".join(where)

        total = await self.session.scalar(
            text(f"SELECT COUNT(*) FROM t_knowledge_base kb WHERE {where_sql}"),
            params,
        )
        result = await self.session.execute(
            text(
                f"""
                SELECT
                    kb.id,
                    kb.name,
                    kb.embedding_model,
                    kb.collection_name,
                    kb.created_by,
                    kb.create_time,
                    kb.update_time,
                    COUNT(doc.id) AS document_count
                FROM t_knowledge_base kb
                LEFT JOIN t_knowledge_document doc
                  ON doc.kb_id = kb.id AND doc.deleted = 0
                WHERE {where_sql}
                GROUP BY kb.id, kb.name, kb.embedding_model, kb.collection_name,
                         kb.created_by, kb.create_time, kb.update_time
                ORDER BY kb.create_time DESC
                LIMIT :limit OFFSET :offset
                """,
            ),
            params,
        )
        return KnowledgeBasePageResponse(
            records=[self._map_kb(row) for row in result.mappings().all()],
            total=int(total or 0),
            size=size,
            current=current,
            pages=ceil(int(total or 0) / size) if total else 0,
        )

    async def get_knowledge_base(self, kb_id: str) -> KnowledgeBaseResponse:
        return self._map_kb(await self._get_knowledge_base(kb_id))

    async def list_chunk_strategies(self) -> list[ChunkStrategyOption]:
        return [
            ChunkStrategyOption(
                value="fixed_size",
                label="固定长度分块",
                defaultConfig={"chunkSize": 800, "overlapSize": 100},
            ),
            ChunkStrategyOption(
                value="structure_aware",
                label="结构感知分块",
                defaultConfig={"targetChars": 1400, "maxChars": 1800, "minChars": 600, "overlapChars": 0},
            ),
        ]

    async def create_knowledge_base(
        self,
        request: KnowledgeBaseCreateRequest,
        user_id: str,
    ) -> KnowledgeBaseResponse:
        kb_id = generate_id()
        collection_name = request.collection_name or f"kb_{kb_id}"
        await self.session.execute(
            text(
                """
                INSERT INTO t_knowledge_base (
                    id, name, embedding_model, collection_name, created_by, updated_by
                )
                VALUES (
                    :id, :name, :embedding_model, :collection_name, :user_id, :user_id
                )
                """,
            ),
            {
                "id": kb_id,
                "name": request.name,
                "embedding_model": request.embedding_model or settings.ai_embedding_default_model,
                "collection_name": collection_name,
                "user_id": user_id,
            },
        )
        await self.session.commit()
        return KnowledgeBaseResponse(
            id=kb_id,
            name=request.name,
            embeddingModel=request.embedding_model or settings.ai_embedding_default_model,
            collectionName=collection_name,
            createdBy=user_id,
        )

    async def update_knowledge_base(
        self,
        kb_id: str,
        request: KnowledgeBaseUpdateRequest,
        user_id: str,
    ) -> KnowledgeBaseResponse:
        current = await self._get_knowledge_base(kb_id)
        name = request.name or current["name"]
        embedding_model = request.embedding_model or current["embedding_model"]
        collection_name = request.collection_name or current["collection_name"]
        await self.session.execute(
            text(
                """
                UPDATE t_knowledge_base
                SET name = :name,
                    embedding_model = :embedding_model,
                    collection_name = :collection_name,
                    updated_by = :user_id,
                    update_time = CURRENT_TIMESTAMP
                WHERE id = :id AND deleted = 0
                """,
            ),
            {
                "id": kb_id,
                "name": name,
                "embedding_model": embedding_model,
                "collection_name": collection_name,
                "user_id": user_id,
            },
        )
        await self.session.commit()
        return KnowledgeBaseResponse(
            id=kb_id,
            name=name,
            embeddingModel=embedding_model,
            collectionName=collection_name,
            createdBy=current["created_by"],
            createTime=current["create_time"],
            updateTime=current["update_time"],
        )

    async def delete_knowledge_base(self, kb_id: str, user_id: str) -> DeleteResponse:
        result = await self.session.execute(
            text(
                """
                UPDATE t_knowledge_base
                SET deleted = 1, updated_by = :user_id, update_time = CURRENT_TIMESTAMP
                WHERE id = :id AND deleted = 0
                """,
            ),
            {"id": kb_id, "user_id": user_id},
        )
        await self.session.commit()
        return DeleteResponse(deleted=result.rowcount > 0)

    async def _get_knowledge_base(self, kb_id: str):
        result = await self.session.execute(
            text(
                """
                SELECT
                    kb.id,
                    kb.name,
                    kb.embedding_model,
                    kb.collection_name,
                    kb.created_by,
                    kb.create_time,
                    kb.update_time,
                    COUNT(doc.id) AS document_count
                FROM t_knowledge_base kb
                LEFT JOIN t_knowledge_document doc
                  ON doc.kb_id = kb.id AND doc.deleted = 0
                WHERE kb.id = :id AND kb.deleted = 0
                GROUP BY kb.id, kb.name, kb.embedding_model, kb.collection_name,
                         kb.created_by, kb.create_time, kb.update_time
                """,
            ),
            {"id": kb_id},
        )
        row = result.mappings().first()
        if row is None:
            raise RagentException(message="知识库不存在", code="KB_NOT_FOUND", status_code=404)
        return row

    @staticmethod
    def _map_kb(row) -> KnowledgeBaseResponse:
        return KnowledgeBaseResponse(
            id=str(row["id"]),
            name=row["name"],
            embeddingModel=row["embedding_model"],
            collectionName=row["collection_name"],
            createdBy=str(row["created_by"]) if row["created_by"] is not None else None,
            documentCount=int(row.get("document_count") or 0),
            createTime=row.get("create_time"),
            updateTime=row.get("update_time"),
        )
