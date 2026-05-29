from pathlib import Path

from app.ingestion.context import ParsedDocument
from app.ingestion.parser.base import DocumentParser


class MarkdownParser(DocumentParser):
    supported_types = {"md", "markdown"}

    async def parse(self, path: Path) -> ParsedDocument:
        text = path.read_text(encoding="utf-8")
        return ParsedDocument(text=text, metadata={"parser": "markdown"})
