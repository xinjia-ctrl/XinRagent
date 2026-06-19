import hashlib
import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.ids import generate_id
from app.core.exceptions import RagentException
from app.infra_ai.embedding import EmbeddingRequest, RoutingEmbeddingService
from app.ingestion.context import IngestionContext
from app.ingestion.nodes.base import NodeConfig, NodeResult
from app.ingestion.nodes.text_enrichment import json_safe_metadata


class IndexerNode:
    node_type = "indexer"

    def __init__(self, session: AsyncSession, embedding_service: RoutingEmbeddingService) -> None:
        self.session = session
        self.embedding_service = embedding_service

    async def execute(self, context: IngestionContext, config: NodeConfig) -> NodeResult:
        if not context.chunks:
            return NodeResult(node_type=self.node_type, success=True, message="indexed:0")

        embedding_model = str(
            config.options.get("embeddingModel")
            or config.options.get("embedding_model")
            or context.metadata.get("embedding_model")
            or "",
        )
        response = await self.embedding_service.embed(
            EmbeddingRequest(texts=context.chunks, model=embedding_model),
        )
        if len(response.vectors) != len(context.chunks):
            raise RagentException(message="Embedding 返回数量与分块数量不一致", code="INGESTION_EMBEDDING_MISMATCH")

        metadata_fields = self._metadata_fields(config.options.get("metadataFields"))
        for index, (chunk, vector) in enumerate(zip(context.chunks, response.vectors, strict=True)):
            chunk_id = generate_id()
            await self._insert_chunk(context, chunk_id, index, chunk)
            await self._insert_vector(context, chunk_id, index, chunk, vector, metadata_fields)

        await self.session.flush()
        return NodeResult(node_type=self.node_type, success=True, message=f"indexed:{len(context.chunks)}")

    async def _insert_chunk(self, context: IngestionContext, chunk_id: str, index: int, content: str) -> None:
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
                "kb_id": context.kb_id,
                "doc_id": context.doc_id,
                "chunk_index": index,
                "content": content,
                "content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                "char_count": len(content),
                "token_count": len(content.split()),
                "user_id": context.user_id,
            },
        )

    async def _insert_vector(
        self,
        context: IngestionContext,
        chunk_id: str,
        index: int,
        content: str,
        vector: list[float],
        metadata_fields: list[str],
    ) -> None:
        await self.session.execute(
            text(
                """
                INSERT INTO t_knowledge_vector (id, content, metadata, embedding)
                VALUES (:id, :content, CAST(:metadata AS jsonb), CAST(:embedding AS vector))
                """,
            ),
            {
                "id": chunk_id,
                "content": content,
                "metadata": json.dumps(self._vector_metadata(context, index, metadata_fields), ensure_ascii=False),
                "embedding": self._vector_literal(vector),
            },
        )

    def _vector_metadata(self, context: IngestionContext, index: int, metadata_fields: list[str]) -> dict:
        base_metadata = {
            "kbId": context.kb_id,
            "docId": context.doc_id,
            "fileName": context.file_name,
            "chunkIndex": index,
        }
        source_metadata = self._select_metadata(context.metadata, metadata_fields)
        chunk_metadata = context.chunk_metadata[index] if index < len(context.chunk_metadata) else {}
        return json_safe_metadata({**base_metadata, **source_metadata, **chunk_metadata})

    @staticmethod
    def _select_metadata(metadata: dict, metadata_fields: list[str]) -> dict:
        if metadata_fields:
            return {field: metadata[field] for field in metadata_fields if field in metadata}
        return {
            key: value
            for key, value in metadata.items()
            if key not in {"credentials"} and not key.lower().endswith("content")
        }

    @staticmethod
    def _metadata_fields(value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [item.strip() for item in str(value).split(",") if item.strip()]

    @staticmethod
    def _vector_literal(vector: list[float]) -> str:
        return "[" + ",".join(str(value) for value in vector) + "]"
