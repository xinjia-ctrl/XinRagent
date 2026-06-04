from app.core.exceptions import RagentException
from app.ingestion.chunker.fixed_size_chunker import FixedSizeChunker
from app.ingestion.context import IngestionContext
from app.ingestion.nodes.base import NodeConfig, NodeResult


class ChunkerNode:
    node_type = "chunker"

    def __init__(self, chunker: FixedSizeChunker | None = None) -> None:
        self.chunker = chunker or FixedSizeChunker()

    async def execute(self, context: IngestionContext, _: NodeConfig) -> NodeResult:
        if context.parsed_document is None:
            raise RagentException(message="文档尚未解析，无法分块", code="INGESTION_NOT_PARSED")

        chunker = self.chunker
        if _.options:
            chunker = FixedSizeChunker(
                chunk_size=int(_.options.get("chunkSize") or _.options.get("chunk_size") or self.chunker.chunk_size),
                overlap=int(_.options.get("overlap") or self.chunker.overlap),
            )
        context.chunks = chunker.split(context.parsed_document.text)
        return NodeResult(
            node_type=self.node_type,
            success=True,
            message=f"chunked:{len(context.chunks)}",
            output={"chunkCount": len(context.chunks)},
        )
