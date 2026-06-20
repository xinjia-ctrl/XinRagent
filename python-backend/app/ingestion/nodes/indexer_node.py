import hashlib

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.ids import generate_id
from app.core.config import settings
from app.core.exceptions import RagentException
from app.infra_ai.embedding import EmbeddingRequest, RoutingEmbeddingService
from app.ingestion.context import IngestionContext
from app.ingestion.nodes.base import NodeConfig, NodeResult
from app.ingestion.nodes.text_enrichment import json_safe_metadata
from app.rag.retrieve import VectorIndexChunk, VectorStoreService, create_vector_store


class IndexerNode:
    node_type = "indexer"

    def __init__(
        self,
        session: AsyncSession,
        embedding_service: RoutingEmbeddingService,
        vector_store: VectorStoreService | None = None,
    ) -> None:
        self.session = session
        self.embedding_service = embedding_service
        self.vector_store = vector_store or create_vector_store(
            session=session,
            embedding_service=embedding_service,
        )

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
        collection_name = await self._resolve_collection_name(context)
        vector_chunks: list[VectorIndexChunk] = []
        for index, (chunk, vector) in enumerate(zip(context.chunks, response.vectors, strict=True)):
            chunk_id = generate_id()
            metadata = self._vector_metadata(context, index, metadata_fields)
            await self._insert_chunk(context, chunk_id, index, chunk)
            vector_chunks.append(
                VectorIndexChunk(
                    id=chunk_id,
                    content=chunk,
                    vector=vector,
                    metadata=metadata,
                ),
            )

        await self.vector_store.index_chunks(collection_name, vector_chunks)
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

    async def _resolve_collection_name(self, context: IngestionContext) -> str:
        explicit = context.metadata.get("collectionName") or context.metadata.get("collection_name")
        if explicit:
            return str(explicit)
        if settings.rag_vector_type.lower() != "milvus":
            return settings.rag_default_collection_name
        result = await self.session.execute(
            text(
                """
                SELECT collection_name
                FROM t_knowledge_base
                WHERE id = :kb_id AND deleted = 0
                """,
            ),
            {"kb_id": context.kb_id},
        )
        row = result.mappings().first()
        if row and row.get("collection_name"):
            return str(row["collection_name"])
        return settings.rag_default_collection_name

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
