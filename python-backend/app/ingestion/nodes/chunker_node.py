from app.core.exceptions import RagentException
from app.ingestion.chunker.fixed_size_chunker import FixedSizeChunker
from app.ingestion.chunker.structure_aware_chunker import StructureAwareChunker
from app.ingestion.context import IngestionContext
from app.ingestion.nodes.base import NodeConfig, NodeResult


class ChunkerNode:
    node_type = "chunker"

    def __init__(self, chunker: FixedSizeChunker | None = None) -> None:
        self.chunker = chunker or FixedSizeChunker()

    async def execute(self, context: IngestionContext, config: NodeConfig) -> NodeResult:
        if context.parsed_document is None:
            raise RagentException(message="文档尚未解析，无法分块", code="INGESTION_NOT_PARSED")

        options = config.options or {}
        strategy = str(options.get("strategy") or "fixed_size").lower()
        chunk_size = self._int_option(options, "chunkSize", "chunk_size", default=self.chunker.chunk_size)
        if chunk_size == -1:
            text = context.parsed_document.text.strip()
            context.chunks = [text] if text else []
            context.chunk_metadata = [
                {"chunkIndex": index, "chunkStrategy": "no_chunk"} for index, _ in enumerate(context.chunks)
            ]
            return NodeResult(
                node_type=self.node_type,
                success=True,
                message=f"chunked:{len(context.chunks)}",
                output={"chunkCount": len(context.chunks), "strategy": "no_chunk"},
            )
        if chunk_size <= 0:
            raise RagentException(message="chunkSize 必须大于 0 或等于 -1", code="INGESTION_CHUNK_SIZE_INVALID")

        context.chunks = self._build_chunker(strategy, chunk_size, options).split(context.parsed_document.text)
        context.chunk_metadata = [
            {"chunkIndex": index, "chunkStrategy": strategy} for index, _ in enumerate(context.chunks)
        ]
        return NodeResult(
            node_type=self.node_type,
            success=True,
            message=f"chunked:{len(context.chunks)}",
            output={"chunkCount": len(context.chunks), "strategy": strategy},
        )

    def _build_chunker(self, strategy: str, chunk_size: int, options: dict) -> FixedSizeChunker | StructureAwareChunker:
        if strategy in {"structure_aware", "markdown_heading"}:
            return StructureAwareChunker(
                target_chars=self._int_option(options, "targetChars", "target_chars", default=chunk_size),
                max_chars=self._int_option(options, "maxChars", "max_chars", "maxChunkSize", default=chunk_size),
                min_chars=self._int_option(options, "minChars", "min_chars", default=max(1, min(chunk_size, 600))),
                overlap_chars=self._int_option(options, "overlapChars", "overlapSize", "overlap", default=0),
                separator=str(options.get("separator") or "\n\n"),
            )
        return FixedSizeChunker(
            chunk_size=chunk_size,
            overlap=self._int_option(options, "overlapSize", "overlap_size", "overlap", default=self.chunker.overlap),
        )

    @staticmethod
    def _int_option(options: dict, *keys: str, default: int) -> int:
        for key in keys:
            value = options.get(key)
            if value is not None and value != "":
                return int(value)
        return default
