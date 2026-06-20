from dataclasses import dataclass, field
import json
from typing import Any, Protocol

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import RagentException
from app.infra_ai.embedding import EmbeddingRequest, RoutingEmbeddingService


@dataclass(frozen=True)
class RetrievedChunk:
    id: str
    content: str
    score: float
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class VectorCollectionSpec:
    name: str
    dimension: int = settings.rag_default_dimension
    metric_type: str = "COSINE"


@dataclass(frozen=True)
class VectorIndexChunk:
    id: str
    content: str
    vector: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)


class VectorStoreService(Protocol):
    async def search(
        self,
        query: str,
        top_k: int | None = None,
        kb_id: str | None = None,
        collection_name: str | None = None,
    ) -> list[RetrievedChunk]: ...

    async def ensure_collection(self, spec: VectorCollectionSpec) -> None: ...

    async def drop_collection(self, collection_name: str) -> None: ...

    async def index_chunks(self, collection_name: str, chunks: list[VectorIndexChunk]) -> None: ...


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

    async def search(
        self,
        query: str,
        top_k: int | None = None,
        kb_id: str | None = None,
        collection_name: str | None = None,
    ) -> list[RetrievedChunk]:
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
              AND (:kb_id IS NULL OR metadata ->> 'kbId' = :kb_id)
              AND (:collection_name IS NULL OR metadata ->> 'collectionName' = :collection_name)
            ORDER BY embedding <=> CAST(:query_vector AS vector)
            LIMIT :top_k
            """,
        )
        result = await self.session.execute(
            statement,
            {
                "query_vector": self._vector_literal(query_vector),
                "top_k": limit,
                "kb_id": kb_id,
                "collection_name": collection_name,
            },
        )
        return [
            RetrievedChunk(
                id=str(row["id"]),
                content=row["content"] or "",
                score=float(row["score"] or 0.0),
                metadata=self._metadata(row["metadata"]),
            )
            for row in result.mappings().all()
        ]

    async def ensure_collection(self, spec: VectorCollectionSpec) -> None:
        return None

    async def drop_collection(self, collection_name: str) -> None:
        return None

    async def index_chunks(self, collection_name: str, chunks: list[VectorIndexChunk]) -> None:
        for chunk in chunks:
            await self.session.execute(
                text(
                    """
                    INSERT INTO t_knowledge_vector (id, content, metadata, embedding)
                    VALUES (:id, :content, CAST(:metadata AS jsonb), CAST(:embedding AS vector))
                    """,
                ),
                {
                    "id": chunk.id,
                    "content": chunk.content,
                    "metadata": json.dumps(
                        {**chunk.metadata, "collectionName": collection_name},
                        ensure_ascii=False,
                    ),
                    "embedding": self._vector_literal(chunk.vector),
                },
            )

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

    @staticmethod
    def _metadata(value: object) -> dict:
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            return json.loads(value)
        return dict(value)


class MilvusVectorStoreService:
    def __init__(
        self,
        embedding_service: RoutingEmbeddingService | None = None,
        *,
        client: Any | None = None,
        collection_name: str | None = None,
        embedding_model: str | None = None,
        dimension: int | None = None,
    ) -> None:
        self.embedding_service = embedding_service
        self._client = client
        self.collection_name = collection_name or self._collection_name(settings.rag_default_collection_name)
        self.embedding_model = embedding_model or settings.ai_embedding_default_model
        self.dimension = dimension or settings.rag_default_dimension

    async def search(
        self,
        query: str,
        top_k: int | None = None,
        kb_id: str | None = None,
        collection_name: str | None = None,
    ) -> list[RetrievedChunk]:
        if self.embedding_service is None:
            raise RagentException(message="Milvus 检索需要 Embedding 服务", code="MILVUS_EMBEDDING_REQUIRED")
        response = await self.embedding_service.embed(EmbeddingRequest(texts=[query], model=self.embedding_model))
        if not response.vectors:
            return []
        resolved_collection = self._collection_name(collection_name or self.collection_name)
        await self.ensure_collection(
            VectorCollectionSpec(
                name=resolved_collection,
                dimension=self.dimension,
                metric_type=settings.milvus_metric_type,
            ),
        )
        filter_expr = f'metadata["kbId"] == "{kb_id}"' if kb_id else ""
        raw_results = self.client.search(
            collection_name=resolved_collection,
            data=[response.vectors[0]],
            limit=top_k or settings.rag_default_top_k,
            filter=filter_expr,
            output_fields=["content", "metadata", "kbId", "docId", "fileName"],
        )
        return [self._to_chunk(item) for item in self._flatten_results(raw_results)]

    async def ensure_collection(self, spec: VectorCollectionSpec) -> None:
        collection_name = self._collection_name(spec.name)
        if self.client.has_collection(collection_name):
            return
        schema = self._build_schema(spec.dimension)
        index_params = self._build_index_params(spec.metric_type)
        if schema is None:
            self.client.create_collection(
                collection_name=collection_name,
                dimension=spec.dimension,
                metric_type=spec.metric_type,
                auto_id=False,
            )
            return
        self.client.create_collection(
            collection_name=collection_name,
            schema=schema,
            index_params=index_params,
            consistency_level="Bounded",
        )

    async def drop_collection(self, collection_name: str) -> None:
        resolved_collection = self._collection_name(collection_name)
        if self.client.has_collection(resolved_collection):
            self.client.drop_collection(resolved_collection)

    async def index_chunks(self, collection_name: str, chunks: list[VectorIndexChunk]) -> None:
        if not chunks:
            return
        await self.ensure_collection(
            VectorCollectionSpec(
                name=collection_name,
                dimension=len(chunks[0].vector) or self.dimension,
                metric_type=settings.milvus_metric_type,
            ),
        )
        rows = [
            {
                "id": chunk.id,
                "content": chunk.content[:65535],
                "metadata": {**chunk.metadata, "collectionName": collection_name},
                "embedding": chunk.vector,
            }
            for chunk in chunks
        ]
        resolved_collection = self._collection_name(collection_name)
        if hasattr(self.client, "upsert"):
            self.client.upsert(collection_name=resolved_collection, data=rows)
            return
        self.client.insert(collection_name=resolved_collection, data=rows)

    @property
    def client(self):
        if self._client is None:
            self._client = self._create_client()
        return self._client

    @staticmethod
    def _create_client():
        try:
            from pymilvus import MilvusClient
        except ImportError as exc:
            raise RagentException(
                message="Milvus SDK 未安装，请安装 pymilvus 或切换 RAG_VECTOR_TYPE=pg",
                code="MILVUS_CLIENT_MISSING",
                status_code=500,
            ) from exc
        kwargs = {"uri": settings.milvus_uri, "db_name": settings.milvus_db_name}
        if settings.milvus_token:
            kwargs["token"] = settings.milvus_token
        return MilvusClient(**kwargs)

    @staticmethod
    def _flatten_results(raw_results: Any) -> list[Any]:
        if not raw_results:
            return []
        if isinstance(raw_results, list) and raw_results and isinstance(raw_results[0], list):
            return raw_results[0]
        return list(raw_results)

    @staticmethod
    def _to_chunk(hit: Any) -> RetrievedChunk:
        if not isinstance(hit, dict):
            return RetrievedChunk(id=str(hit), content="", score=0.0, metadata={})
        entity = hit.get("entity", hit)
        metadata = entity.get("metadata") or {}
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        chunk_id = str(hit.get("id") or entity.get("id") or entity.get("chunkId"))
        return RetrievedChunk(
            id=chunk_id,
            content=entity.get("content") or hit.get("content") or "",
            score=float(hit.get("score") or hit.get("distance") or 0.0),
            metadata=dict(metadata),
        )

    @staticmethod
    def _collection_name(collection_name: str) -> str:
        prefix = settings.milvus_collection_prefix
        if collection_name.startswith(prefix):
            return collection_name
        return f"{prefix}{collection_name}"

    def _build_schema(self, dimension: int):
        if not hasattr(self.client, "create_schema"):
            return None
        try:
            from pymilvus import DataType
        except ImportError:
            return None
        schema = self.client.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field("id", DataType.VARCHAR, is_primary=True, max_length=64)
        schema.add_field("content", DataType.VARCHAR, max_length=65535)
        schema.add_field("metadata", DataType.JSON)
        schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=dimension)
        return schema

    def _build_index_params(self, metric_type: str):
        if not hasattr(self.client, "prepare_index_params"):
            return None
        index_params = self.client.prepare_index_params()
        index_params.add_index(
            field_name="embedding",
            index_type="HNSW",
            metric_type=metric_type,
            params={"M": 48, "efConstruction": 200},
        )
        return index_params


class VectorSpaceManager:
    def __init__(self, vector_store: VectorStoreService | None = None) -> None:
        self.vector_store = vector_store

    async def ensure_collection(self, collection_name: str, dimension: int | None = None) -> None:
        if self.vector_store is None:
            return
        await self.vector_store.ensure_collection(
            VectorCollectionSpec(
                name=collection_name,
                dimension=dimension or settings.rag_default_dimension,
                metric_type=settings.milvus_metric_type,
            ),
        )

    async def drop_collection(self, collection_name: str) -> None:
        if self.vector_store is None:
            return
        await self.vector_store.drop_collection(collection_name)


def create_vector_store(
    *,
    session: AsyncSession,
    embedding_service: RoutingEmbeddingService,
) -> VectorStoreService:
    if settings.rag_vector_type.lower() == "milvus":
        return MilvusVectorStoreService(embedding_service=embedding_service)
    return PgVectorStoreService(session=session, embedding_service=embedding_service)


def create_vector_space_manager() -> VectorSpaceManager:
    if settings.rag_vector_type.lower() != "milvus":
        return VectorSpaceManager()
    return VectorSpaceManager(MilvusVectorStoreService())
