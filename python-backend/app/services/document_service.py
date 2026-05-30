from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import RagentException
from app.schemas.document import KnowledgeChunkResponse, KnowledgeDocumentResponse


class DocumentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_documents(self, kb_id: str) -> list[KnowledgeDocumentResponse]:
        result = await self.session.execute(
            text(
                """
                SELECT id, kb_id, doc_name, file_url, file_type, file_size, status, chunk_count
                FROM t_knowledge_document
                WHERE kb_id = :kb_id AND deleted = 0
                ORDER BY create_time DESC
                """,
            ),
            {"kb_id": kb_id},
        )
        return [self._map_document(row) for row in result.mappings().all()]

    async def get_document(self, doc_id: str) -> KnowledgeDocumentResponse:
        result = await self.session.execute(
            text(
                """
                SELECT id, kb_id, doc_name, file_url, file_type, file_size, status, chunk_count
                FROM t_knowledge_document
                WHERE id = :doc_id AND deleted = 0
                """,
            ),
            {"doc_id": doc_id},
        )
        row = result.mappings().first()
        if row is None:
            raise RagentException(message="文档不存在", code="DOCUMENT_NOT_FOUND", status_code=404)
        return self._map_document(row)

    async def list_chunks(self, doc_id: str) -> list[KnowledgeChunkResponse]:
        result = await self.session.execute(
            text(
                """
                SELECT id, kb_id, doc_id, chunk_index, content, char_count, token_count
                FROM t_knowledge_chunk
                WHERE doc_id = :doc_id AND deleted = 0
                ORDER BY chunk_index ASC
                """,
            ),
            {"doc_id": doc_id},
        )
        return [
            KnowledgeChunkResponse(
                id=str(row["id"]),
                kb_id=str(row["kb_id"]),
                doc_id=str(row["doc_id"]),
                chunk_index=row["chunk_index"],
                content=row["content"],
                char_count=row["char_count"],
                token_count=row["token_count"],
            )
            for row in result.mappings().all()
        ]

    @staticmethod
    def _map_document(row) -> KnowledgeDocumentResponse:
        return KnowledgeDocumentResponse(
            id=str(row["id"]),
            kb_id=str(row["kb_id"]),
            doc_name=row["doc_name"],
            file_url=row["file_url"],
            file_type=row["file_type"],
            file_size=row["file_size"],
            status=row["status"],
            chunk_count=row["chunk_count"] or 0,
        )
