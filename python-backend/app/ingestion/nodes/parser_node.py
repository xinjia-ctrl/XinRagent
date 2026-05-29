from app.core.exceptions import RagentException
from app.ingestion.context import IngestionContext
from app.ingestion.nodes.base import NodeConfig, NodeResult
from app.ingestion.parser.base import DocumentParser
from app.ingestion.parser.markdown_parser import MarkdownParser
from app.ingestion.parser.text_parser import TextParser


class ParserNode:
    node_type = "parser"

    def __init__(self, parsers: list[DocumentParser] | None = None) -> None:
        self.parsers = parsers or [MarkdownParser(), TextParser()]

    async def execute(self, context: IngestionContext, _: NodeConfig) -> NodeResult:
        parser = self._find_parser(context.file_type)
        if parser is None:
            raise RagentException(message=f"不支持的文档类型: {context.file_type}", code="INGESTION_UNSUPPORTED_FILE")

        context.parsed_document = await parser.parse(context.file_path)
        context.metadata.update(context.parsed_document.metadata)
        return NodeResult(node_type=self.node_type, success=True, message="parsed")

    def _find_parser(self, file_type: str) -> DocumentParser | None:
        normalized = file_type.lower().removeprefix(".")
        for parser in self.parsers:
            if normalized in parser.supported_types:
                return parser
        return None
