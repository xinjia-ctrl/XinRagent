from pathlib import Path
from typing import Protocol

from app.ingestion.context import ParsedDocument


class DocumentParser(Protocol):
    supported_types: set[str]

    async def parse(self, path: Path) -> ParsedDocument:
        ...
