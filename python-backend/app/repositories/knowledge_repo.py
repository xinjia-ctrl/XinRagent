from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgeBase, KnowledgeChunk, KnowledgeDocument, KnowledgeVector
from app.repositories.base import BaseRepository


class KnowledgeBaseRepository(BaseRepository[KnowledgeBase]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, KnowledgeBase)


class KnowledgeDocumentRepository(BaseRepository[KnowledgeDocument]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, KnowledgeDocument)

    async def list_by_kb(self, kb_id: str, limit: int = 50) -> Sequence[KnowledgeDocument]:
        statement = select(KnowledgeDocument).where(KnowledgeDocument.kb_id == kb_id).limit(limit)
        result = await self.session.scalars(statement)
        return result.all()


class KnowledgeChunkRepository(BaseRepository[KnowledgeChunk]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, KnowledgeChunk)

    async def list_by_document(self, doc_id: str, limit: int = 100) -> Sequence[KnowledgeChunk]:
        statement = (
            select(KnowledgeChunk)
            .where(KnowledgeChunk.doc_id == doc_id)
            .order_by(KnowledgeChunk.chunk_index.asc())
            .limit(limit)
        )
        result = await self.session.scalars(statement)
        return result.all()


class KnowledgeVectorRepository(BaseRepository[KnowledgeVector]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, KnowledgeVector)
