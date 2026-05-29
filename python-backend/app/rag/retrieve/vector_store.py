from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.infra_ai.embedding import EmbeddingRequest, RoutingEmbeddingService


@dataclass(frozen=True)
class RetrievedChunk:
    id: str
    content: str
    score: float
    metadata: dict = field(default_factory=dict)


class PgVectorStoreService:
    def __init__(
        self,
        session: AsyncSession,
        embedding_service: RoutingEmbeddingService,
        embedding_model: str | None = None,
    ) -> None:
        self.session = session
        self.embedding_service = embedding_service
        self.embedding_model = embedding_model or settings.ai_embedding_default_model

    async def search(self, query: str, top_k: int | None = None) -> list[RetrievedChunk]:
        limit = top_k or settings.rag_default_top_k
        query_vector = await self._embed_query(query)
        if not query_vector:
            return []

        statement = text(
            """
            SELECT
                id,
                content,
                metadata,
                1 - (embedding <=> CAST(:query_vector AS vector)) AS score
            FROM t_knowledge_vector
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:query_vector AS vector)
            LIMIT :top_k
            """,
        )
        result = await self.session.execute(
            statement,
            {"query_vector": self._vector_literal(query_vector), "top_k": limit},
        )
        return [
            RetrievedChunk(
                id=str(row["id"]),
                content=row["content"] or "",
                score=float(row["score"] or 0.0),
                metadata=row["metadata"] or {},
            )
            for row in result.mappings().all()
        ]

    async def _embed_query(self, query: str) -> list[float]:
        response = await self.embedding_service.embed(
            EmbeddingRequest(texts=[query], model=self.embedding_model),
        )
        if not response.vectors:
            return []
        return response.vectors[0]

    @staticmethod
    def _vector_literal(vector: list[float]) -> str:
        return "[" + ",".join(str(value) for value in vector) + "]"
