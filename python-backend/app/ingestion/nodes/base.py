from dataclasses import dataclass, field
from typing import Protocol

from app.ingestion.context import IngestionContext


@dataclass(frozen=True)
class NodeConfig:
    node_id: str | None = None
    node_type: str | None = None
    next_node_id: str | None = None
    condition: dict | None = None
    options: dict = field(default_factory=dict)


@dataclass(frozen=True)
class NodeResult:
    node_type: str
    success: bool
    message: str = ""
    should_continue: bool = True
    output: dict = field(default_factory=dict)
    error: str | None = None

    @classmethod
    def skipped(cls, node_type: str, message: str = "condition skipped") -> "NodeResult":
        return cls(node_type=node_type, success=True, message=message, output={"skipped": True})


class IngestionNode(Protocol):
    node_type: str

    async def execute(self, context: IngestionContext, config: NodeConfig) -> NodeResult:
        ...
