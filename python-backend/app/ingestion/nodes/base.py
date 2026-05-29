from dataclasses import dataclass, field
from typing import Protocol

from app.ingestion.context import IngestionContext


@dataclass(frozen=True)
class NodeConfig:
    options: dict = field(default_factory=dict)


@dataclass(frozen=True)
class NodeResult:
    node_type: str
    success: bool
    message: str = ""


class IngestionNode(Protocol):
    node_type: str

    async def execute(self, context: IngestionContext, config: NodeConfig) -> NodeResult:
        ...
