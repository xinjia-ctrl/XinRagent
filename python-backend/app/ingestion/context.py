from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ParsedDocument:
    text: str
    metadata: dict = field(default_factory=dict)


@dataclass
class IngestionContext:
    kb_id: str
    doc_id: str
    file_name: str
    file_path: Path
    file_type: str
    user_id: str
    parsed_document: ParsedDocument | None = None
    chunks: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    status: str = "pending"
    logs: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
