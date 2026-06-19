from typing import Any

from app.ingestion.context import IngestionContext
from app.ingestion.nodes.base import NodeConfig, NodeResult
from app.ingestion.nodes.text_enrichment import (
    extract_keywords,
    scalar_document_metadata,
    summarize_text,
)


class EnricherNode:
    node_type = "enricher"

    async def execute(self, context: IngestionContext, config: NodeConfig) -> NodeResult:
        if not context.chunks:
            context.chunk_metadata = []
            return NodeResult(node_type=self.node_type, success=True, message="enriched:0")

        options = config.options or {}
        attach_document_metadata = bool(options.get("attachDocumentMetadata", True))
        task_types = self._task_types(options.get("tasks"))
        document_metadata = scalar_document_metadata(context.metadata) if attach_document_metadata else {}
        context.chunk_metadata = self._ensure_chunk_metadata(context)

        for index, chunk in enumerate(context.chunks):
            metadata = context.chunk_metadata[index]
            metadata.update({"chunkIndex": index})
            metadata.update(document_metadata)
            for task_type in task_types:
                if task_type == "metadata":
                    metadata.update(
                        {
                            "chunkCharCount": len(chunk),
                            "chunkTokenCount": len(chunk.split()),
                        },
                    )
                elif task_type == "keywords":
                    metadata["chunkKeywords"] = extract_keywords(chunk, limit=5)
                elif task_type == "summary":
                    metadata["chunkSummary"] = summarize_text(chunk, max_length=160)
                elif task_type == "metadata_fields":
                    continue

        return NodeResult(
            node_type=self.node_type,
            success=True,
            message=f"enriched:{len(context.chunk_metadata)}",
            output={
                "chunkCount": len(context.chunk_metadata),
                "tasks": task_types,
                "attachDocumentMetadata": attach_document_metadata,
            },
        )

    @staticmethod
    def _ensure_chunk_metadata(context: IngestionContext) -> list[dict[str, Any]]:
        existing = list(context.chunk_metadata)
        while len(existing) < len(context.chunks):
            existing.append({})
        return existing[: len(context.chunks)]

    @staticmethod
    def _task_types(tasks: Any) -> list[str]:
        if not isinstance(tasks, list):
            return []
        result: list[str] = []
        for task in tasks:
            if isinstance(task, dict) and task.get("type"):
                result.append(str(task["type"]).strip())
        return result
