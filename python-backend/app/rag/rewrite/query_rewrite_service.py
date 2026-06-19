from dataclasses import dataclass, field
import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.infra_ai.chat import ChatMessage, ChatRequest, RoutingLLMService
from app.rag.llm_json import compact_json, parse_json_object


@dataclass(frozen=True)
class AppliedMapping:
    source_term: str
    target_term: str


@dataclass(frozen=True)
class RewriteResult:
    original_question: str
    rewritten_question: str
    sub_questions: list[str]
    applied_mappings: list[AppliedMapping] = field(default_factory=list)
    strategy: str = "rule"


class QueryRewriteService:
    def __init__(
        self,
        session: AsyncSession | None = None,
        llm_service: RoutingLLMService | None = None,
        model: str | None = None,
    ) -> None:
        self.session = session
        self.llm_service = llm_service
        self.model = model or settings.ai_chat_default_model

    async def rewrite_with_split(
        self,
        question: str,
        history: list[ChatMessage] | None = None,
    ) -> RewriteResult:
        mappings = await self._load_mappings()
        rewritten, applied = self._apply_mappings(question.strip(), mappings)

        llm_result = await self._rewrite_with_llm(
            original_question=question,
            mapped_question=rewritten,
            history=history or [],
            mappings=mappings,
            applied=applied,
        )
        if llm_result is not None:
            return llm_result

        sub_questions = self._split_questions(rewritten)
        if not sub_questions:
            sub_questions = [rewritten]

        return RewriteResult(
            original_question=question,
            rewritten_question=rewritten,
            sub_questions=sub_questions,
            applied_mappings=applied,
            strategy="rule",
        )

    async def _load_mappings(self) -> list[dict]:
        if self.session is None:
            return []
        result = await self.session.execute(
            text(
                """
                SELECT source_term, target_term, match_type, priority
                FROM t_query_term_mapping
                WHERE enabled = 1 AND deleted = 0
                ORDER BY priority ASC, create_time ASC
                """,
            ),
        )
        return [dict(row) for row in result.mappings().all()]

    @staticmethod
    def _split_questions(question: str) -> list[str]:
        parts = re.split(r"[?？;；\n]+|(?:并且|同时|另外|以及)", question)
        return [part.strip(" ，,。.") for part in parts if part.strip(" ，,。.")]

    @staticmethod
    def _apply_mappings(question: str, mappings: list[dict]) -> tuple[str, list[AppliedMapping]]:
        rewritten = question
        applied: list[AppliedMapping] = []
        for mapping in mappings:
            source = mapping["source_term"]
            target = mapping["target_term"]
            if not source or not target or source not in rewritten:
                continue
            rewritten = rewritten.replace(source, target)
            applied.append(AppliedMapping(source_term=source, target_term=target))
        return rewritten, applied

    async def _rewrite_with_llm(
        self,
        *,
        original_question: str,
        mapped_question: str,
        history: list[ChatMessage],
        mappings: list[dict],
        applied: list[AppliedMapping],
    ) -> RewriteResult | None:
        if self.llm_service is None:
            return None
        mapping_payload = [
            {"sourceTerm": item.get("source_term"), "targetTerm": item.get("target_term")}
            for item in mappings[:50]
        ]
        history_payload = [
            {"role": message.role, "content": message.content}
            for message in history[-6:]
            if message.content
        ]
        prompt = {
            "question": original_question,
            "mappedQuestion": mapped_question,
            "history": history_payload,
            "termMappings": mapping_payload,
            "outputSchema": {
                "rewrittenQuestion": "string",
                "subQuestions": ["string"],
            },
        }
        try:
            response = await self.llm_service.complete(
                ChatRequest(
                    messages=[
                        ChatMessage(
                            role="system",
                            content=(
                                "你是 RAG 查询重写器。请结合历史对话消解指代、补全检索关键词、"
                                "拆分复合问题。只返回 JSON 对象，不要输出解释。"
                            ),
                        ),
                        ChatMessage(role="user", content=compact_json(prompt)),
                    ],
                    model=self.model,
                    temperature=0.0,
                    extra_body={"response_format": {"type": "json_object"}},
                ),
            )
        except Exception:
            return None

        parsed = parse_json_object(response.content)
        if parsed is None:
            return None
        rewritten = str(parsed.get("rewrittenQuestion") or parsed.get("rewritten_question") or "").strip()
        sub_questions = self._normalize_sub_questions(parsed.get("subQuestions") or parsed.get("sub_questions"))
        if not rewritten:
            return None
        if not sub_questions:
            sub_questions = [rewritten]
        return RewriteResult(
            original_question=original_question,
            rewritten_question=rewritten,
            sub_questions=sub_questions,
            applied_mappings=applied,
            strategy="llm",
        )

    @staticmethod
    def _normalize_sub_questions(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip(" ，,。.") for item in value if str(item).strip(" ，,。.")]
