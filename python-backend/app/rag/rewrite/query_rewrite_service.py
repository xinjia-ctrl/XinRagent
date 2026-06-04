from dataclasses import dataclass, field
import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra_ai.chat import ChatMessage


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


class QueryRewriteService:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session

    async def rewrite_with_split(
        self,
        question: str,
        history: list[ChatMessage] | None = None,
    ) -> RewriteResult:
        rewritten = question.strip()
        mappings = await self._load_mappings()
        applied: list[AppliedMapping] = []

        for mapping in mappings:
            source = mapping["source_term"]
            target = mapping["target_term"]
            if not source or not target or source not in rewritten:
                continue
            rewritten = rewritten.replace(source, target)
            applied.append(AppliedMapping(source_term=source, target_term=target))

        sub_questions = self._split_questions(rewritten)
        if not sub_questions:
            sub_questions = [rewritten]

        return RewriteResult(
            original_question=question,
            rewritten_question=rewritten,
            sub_questions=sub_questions,
            applied_mappings=applied,
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
