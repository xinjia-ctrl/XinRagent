from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.ids import generate_id
from app.core.config import settings
from app.schemas.knowledge import (
    DeleteResponse,
    KnowledgeBaseCreateRequest,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdateRequest,
)


class KnowledgeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_knowledge_bases(self) -> list[KnowledgeBaseResponse]:
        result = await self.session.execute(
            text(
                """
                SELECT id, name, embedding_model, collection_name, created_by
                FROM t_knowledge_base
                WHERE deleted = 0
                ORDER BY create_time DESC
                """,
            ),
        )
        return [self._map_kb(row) for row in result.mappings().all()]

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
            embedding_model=request.embedding_model or settings.ai_embedding_default_model,
            collection_name=collection_name,
            created_by=user_id,
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
            embedding_model=embedding_model,
            collection_name=collection_name,
            created_by=current["created_by"],
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
                SELECT id, name, embedding_model, collection_name, created_by
                FROM t_knowledge_base
                WHERE id = :id AND deleted = 0
                """,
            ),
            {"id": kb_id},
        )
        row = result.mappings().first()
        if row is None:
            from app.core.exceptions import RagentException

            raise RagentException(message="知识库不存在", code="KB_NOT_FOUND", status_code=404)
        return row

    @staticmethod
    def _map_kb(row) -> KnowledgeBaseResponse:
        return KnowledgeBaseResponse(
            id=str(row["id"]),
            name=row["name"],
            embedding_model=row["embedding_model"],
            collection_name=row["collection_name"],
            created_by=str(row["created_by"]),
        )
