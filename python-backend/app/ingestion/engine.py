from dataclasses import dataclass

from app.ingestion.context import IngestionContext
from app.ingestion.nodes import ChunkerNode, IndexerNode, NodeConfig, ParserNode


@dataclass(frozen=True)
class IngestionResult:
    doc_id: str
    chunk_count: int
    status: str


class IngestionEngine:
    def __init__(
        self,
        parser_node: ParserNode,
        chunker_node: ChunkerNode,
        indexer_node: IndexerNode,
    ) -> None:
        self.parser_node = parser_node
        self.chunker_node = chunker_node
        self.indexer_node = indexer_node

    async def ingest(self, context: IngestionContext) -> IngestionResult:
        config = NodeConfig()
        await self.parser_node.execute(context, config)
        await self.chunker_node.execute(context, config)
        await self.indexer_node.execute(context, config)
        return IngestionResult(
            doc_id=context.doc_id,
            chunk_count=len(context.chunks),
            status="indexed",
        )
