from dataclasses import dataclass
from time import perf_counter
from typing import Any

from app.core.exceptions import RagentException
from app.ingestion.context import IngestionContext
from app.ingestion.nodes import ChunkerNode, IndexerNode, IngestionNode, NodeConfig, NodeResult, ParserNode


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
        self.node_map: dict[str, IngestionNode] = {
            parser_node.node_type: parser_node,
            chunker_node.node_type: chunker_node,
            indexer_node.node_type: indexer_node,
        }

    async def ingest(
        self,
        context: IngestionContext,
        pipeline_nodes: list[Any] | None = None,
    ) -> IngestionResult:
        if pipeline_nodes:
            await self.execute_pipeline(self._normalize_nodes(pipeline_nodes), context)
        else:
            await self.execute_pipeline(
                [
                    NodeConfig(node_id="parser", node_type="parser", next_node_id="chunker"),
                    NodeConfig(node_id="chunker", node_type="chunker", next_node_id="indexer"),
                    NodeConfig(node_id="indexer", node_type="indexer"),
                ],
                context,
            )
        return IngestionResult(
            doc_id=context.doc_id,
            chunk_count=len(context.chunks),
            status="indexed",
        )

    async def execute_pipeline(self, nodes: list[NodeConfig], context: IngestionContext) -> IngestionContext:
        node_map = {node.node_id: node for node in nodes if node.node_id}
        self._validate_pipeline(node_map)
        current_node_id = self._find_start_node(node_map)
        if not current_node_id:
            raise RagentException(message="流水线未找到起始节点", code="INGESTION_PIPELINE_NO_START")

        context.status = "running"
        executed_count = 0
        max_nodes = len(node_map)
        while current_node_id:
            if executed_count > max_nodes:
                raise RagentException(message="流水线执行超过节点上限", code="INGESTION_PIPELINE_LOOP")
            config = node_map[current_node_id]
            result = await self._execute_node(context, config)
            executed_count += 1
            if not result.success:
                context.status = "failed"
                context.error = result.error or result.message
                break
            if not result.should_continue:
                break
            current_node_id = config.next_node_id

        if context.status == "running":
            context.status = "completed"
        return context

    async def _execute_node(self, context: IngestionContext, config: NodeConfig) -> NodeResult:
        node_type = config.node_type or ""
        node = self.node_map.get(node_type)
        if node is None:
            result = NodeResult(node_type=node_type, success=False, message="node missing", error="未找到节点类型")
            context.logs.append(self._log_entry(config, result, 0))
            return result

        if config.condition and not self._condition_matches(context, config.condition):
            result = NodeResult.skipped(node_type, "条件未满足，跳过节点")
            context.logs.append(self._log_entry(config, result, 0))
            return result

        started_at = perf_counter()
        try:
            result = await node.execute(context, config)
        except Exception as exc:
            result = NodeResult(node_type=node_type, success=False, message=str(exc), error=str(exc))
        duration_ms = int((perf_counter() - started_at) * 1000)
        context.logs.append(self._log_entry(config, result, duration_ms))
        return result

    def _validate_pipeline(self, node_map: dict[str, NodeConfig]) -> None:
        for node_id in node_map:
            seen: set[str] = set()
            current = node_id
            while current:
                if current in seen:
                    raise RagentException(message=f"流水线存在环: {current}", code="INGESTION_PIPELINE_CYCLE")
                seen.add(current)
                config = node_map.get(current)
                if config is None or not config.next_node_id:
                    break
                if config.next_node_id not in node_map:
                    raise RagentException(
                        message=f"找不到下一个节点: {config.next_node_id}",
                        code="INGESTION_PIPELINE_NEXT_NOT_FOUND",
                    )
                current = config.next_node_id

    @staticmethod
    def _find_start_node(node_map: dict[str, NodeConfig]) -> str | None:
        referenced = {node.next_node_id for node in node_map.values() if node.next_node_id}
        return next((node_id for node_id in node_map if node_id not in referenced), None)

    @staticmethod
    def _condition_matches(context: IngestionContext, condition: dict) -> bool:
        field = condition.get("field")
        expected = condition.get("equals")
        if not field:
            return True
        actual = getattr(context, field, context.metadata.get(field))
        return actual == expected

    @staticmethod
    def _log_entry(config: NodeConfig, result: NodeResult, duration_ms: int) -> dict[str, Any]:
        return {
            "nodeId": config.node_id,
            "nodeType": config.node_type,
            "message": result.message,
            "durationMs": duration_ms,
            "success": result.success,
            "error": result.error,
            "output": result.output,
        }

    @staticmethod
    def _normalize_nodes(nodes: list[Any]) -> list[NodeConfig]:
        normalized: list[NodeConfig] = []
        for node in nodes:
            if isinstance(node, NodeConfig):
                normalized.append(node)
                continue
            node_id = getattr(node, "nodeId", None) or getattr(node, "node_id", None)
            node_type = getattr(node, "nodeType", None) or getattr(node, "node_type", None)
            next_node_id = getattr(node, "nextNodeId", None) or getattr(node, "next_node_id", None)
            settings = getattr(node, "settings", None) or {}
            condition = getattr(node, "condition", None)
            normalized.append(
                NodeConfig(
                    node_id=node_id,
                    node_type=node_type,
                    next_node_id=next_node_id,
                    condition=condition,
                    options=settings,
                ),
            )
        return normalized
