from typing import Any

from app.core.exceptions import RagentException
from app.ingestion.context import IngestionContext
from app.ingestion.nodes.base import NodeConfig, NodeResult
from app.ingestion.nodes.text_enrichment import extract_keywords, first_heading_or_line, summarize_text


class EnhancerNode:
    node_type = "enhancer"

    async def execute(self, context: IngestionContext, config: NodeConfig) -> NodeResult:
        if context.parsed_document is None:
            raise RagentException(message="文档尚未解析，无法增强", code="INGESTION_NOT_PARSED")

        text = context.parsed_document.text
        updates: dict[str, Any] = {}
        applied_tasks: list[str] = []
        for task_type in self._task_types(config.options.get("tasks")):
            if task_type == "metadata":
                updates.update(
                    {
                        "title": first_heading_or_line(text, context.file_name),
                        "charCount": len(text),
                        "lineCount": len(text.splitlines()),
                    },
                )
            elif task_type == "keywords":
                updates["keywords"] = extract_keywords(text)
            elif task_type == "questions":
                updates["suggestedQuestions"] = self._suggest_questions(text, context.file_name)
            elif task_type == "context_enhance":
                updates["contextSummary"] = summarize_text(text, max_length=240)
            else:
                continue
            applied_tasks.append(task_type)

        model_id = config.options.get("modelId")
        if model_id:
            updates["enhancerModelId"] = str(model_id)

        context.parsed_document.metadata.update(updates)
        context.metadata.update(updates)
        return NodeResult(
            node_type=self.node_type,
            success=True,
            message=f"enhanced:{len(applied_tasks)}",
            output={"tasks": applied_tasks, "fields": sorted(updates)},
        )

    @staticmethod
    def _task_types(tasks: Any) -> list[str]:
        if not isinstance(tasks, list):
            return []
        result: list[str] = []
        for task in tasks:
            if isinstance(task, dict) and task.get("type"):
                result.append(str(task["type"]).strip())
        return result

    @staticmethod
    def _suggest_questions(text: str, file_name: str) -> list[str]:
        title = first_heading_or_line(text, file_name)
        keywords = extract_keywords(text, limit=3)
        questions = [f"{title} 的核心内容是什么？"]
        if keywords:
            questions.append(f"{title} 中 {keywords[0]} 的作用是什么？")
        questions.append("这份文档有哪些可检索的关键结论？")
        return questions
