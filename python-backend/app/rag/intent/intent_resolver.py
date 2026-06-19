from dataclasses import dataclass
import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.infra_ai.chat import ChatMessage, ChatRequest, RoutingLLMService
from app.rag.llm_json import compact_json, parse_json_object
from app.rag.rewrite import RewriteResult


@dataclass(frozen=True)
class IntentMatch:
    intent_id: str
    intent_code: str
    name: str
    confidence: float
    kb_id: str | None = None
    kind: int = 0
    top_k: int | None = None
    collection_name: str | None = None
    mcp_tool_id: str | None = None
    prompt_snippet: str | None = None
    prompt_template: str | None = None
    reason: str | None = None

    @property
    def is_knowledge(self) -> bool:
        return self.kind == 0 and not self.mcp_tool_id

    @property
    def is_mcp(self) -> bool:
        return bool(self.mcp_tool_id)

    @property
    def is_system(self) -> bool:
        return self.kind == 1


@dataclass(frozen=True)
class IntentResolution:
    matches: list[IntentMatch]
    guidance_prompt: str | None = None

    @property
    def knowledge_matches(self) -> list[IntentMatch]:
        return [match for match in self.matches if match.is_knowledge]

    @property
    def mcp_matches(self) -> list[IntentMatch]:
        return [match for match in self.matches if match.is_mcp]

    @property
    def system_matches(self) -> list[IntentMatch]:
        return [match for match in self.matches if match.is_system]

    @property
    def is_system_only(self) -> bool:
        return bool(self.matches) and all(match.is_system for match in self.matches)


class IntentResolver:
    def __init__(
        self,
        session: AsyncSession | None = None,
        threshold: float = 0.18,
        llm_service: RoutingLLMService | None = None,
        model: str | None = None,
    ) -> None:
        self.session = session
        self.threshold = threshold
        self.llm_service = llm_service
        self.model = model or settings.ai_chat_default_model

    async def resolve(self, rewrite_result: RewriteResult) -> IntentResolution:
        nodes = await self._load_nodes()
        if not nodes:
            return IntentResolution(matches=[])

        llm_resolution = await self._resolve_with_llm(rewrite_result, nodes)
        if llm_resolution is not None:
            return llm_resolution

        return self._resolve_by_rules(rewrite_result, nodes)

    def _resolve_by_rules(self, rewrite_result: RewriteResult, nodes: list[dict]) -> IntentResolution:
        query = rewrite_result.rewritten_question
        scored = [
            self._to_match(node, self._score(query, node))
            for node in nodes
        ]
        matches = [
            match
            for match in sorted(scored, key=lambda item: item.confidence, reverse=True)
            if match.confidence >= self.threshold
        ][:3]
        return IntentResolution(matches=matches, guidance_prompt=self._guidance(matches))

    async def _load_nodes(self) -> list[dict]:
        if self.session is None:
            return []
        result = await self.session.execute(
            text(
                """
                SELECT
                    id, kb_id, intent_code, name, level, parent_code, description,
                    examples, collection_name, top_k, mcp_tool_id, kind,
                    prompt_snippet, prompt_template
                FROM t_intent_node
                WHERE enabled = 1 AND deleted = 0
                ORDER BY level DESC, sort_order ASC, create_time ASC
                """,
            ),
        )
        return [dict(row) for row in result.mappings().all()]

    def _to_match(self, row: dict, confidence: float, reason: str | None = None) -> IntentMatch:
        return IntentMatch(
            intent_id=str(row["id"]),
            intent_code=row["intent_code"],
            name=row["name"],
            confidence=round(confidence, 4),
            kb_id=str(row["kb_id"]) if row.get("kb_id") is not None else None,
            kind=int(row.get("kind") or 0),
            top_k=row.get("top_k"),
            collection_name=row.get("collection_name"),
            mcp_tool_id=row.get("mcp_tool_id"),
            prompt_snippet=row.get("prompt_snippet"),
            prompt_template=row.get("prompt_template"),
            reason=reason,
        )

    def _score(self, query: str, row: dict) -> float:
        normalized_query = query.lower()
        score = 0.0
        name = str(row.get("name") or "").lower()
        description = str(row.get("description") or "").lower()

        if name and name in normalized_query:
            score += 0.45
        score += min(0.25, self._term_overlap(normalized_query, name) * 0.08)
        score += min(0.20, self._term_overlap(normalized_query, description) * 0.05)

        examples = self._split_examples(row.get("examples"))
        for example in examples:
            example_text = example.lower()
            if example_text and example_text in normalized_query:
                score += 0.50
                continue
            score += min(0.20, self._term_overlap(normalized_query, example_text) * 0.05)

        return min(score, 1.0)

    @staticmethod
    def _term_overlap(query: str, text: str) -> int:
        if not query or not text:
            return 0
        terms = {term for term in re.split(r"\W+", text) if len(term) >= 2}
        if not terms:
            return 0
        return sum(1 for term in terms if term in query)

    @staticmethod
    def _split_examples(value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value if str(item).strip()]
        return [item.strip() for item in str(value).splitlines() if item.strip()]

    @staticmethod
    def _guidance(matches: list[IntentMatch]) -> str | None:
        if len(matches) < 2:
            return None
        first, second = matches[0], matches[1]
        if first.confidence >= 0.55 or first.confidence - second.confidence > 0.08:
            return None
        return f"你的问题可能属于“{first.name}”或“{second.name}”，请补充具体业务场景后我再继续。"

    async def _resolve_with_llm(
        self,
        rewrite_result: RewriteResult,
        nodes: list[dict],
    ) -> IntentResolution | None:
        if self.llm_service is None:
            return None
        node_payload = [
            {
                "intentId": str(row["id"]),
                "intentCode": row.get("intent_code"),
                "name": row.get("name"),
                "description": row.get("description"),
                "examples": self._split_examples(row.get("examples")),
                "kind": int(row.get("kind") or 0),
                "kbId": str(row["kb_id"]) if row.get("kb_id") is not None else None,
                "mcpToolId": row.get("mcp_tool_id"),
            }
            for row in nodes[:80]
        ]
        prompt = {
            "rewrittenQuestion": rewrite_result.rewritten_question,
            "subQuestions": rewrite_result.sub_questions,
            "candidateIntents": node_payload,
            "outputSchema": {
                "matches": [{"intentCode": "string", "confidence": "0-1 number", "reason": "string"}],
                "guidancePrompt": "string|null",
            },
        }
        try:
            response = await self.llm_service.complete(
                ChatRequest(
                    messages=[
                        ChatMessage(
                            role="system",
                            content=(
                                "你是 RAG 意图路由器。请只从候选意图中选择最匹配的 1 到 3 个，"
                                "区分知识库、系统回答和 MCP 工具意图。只返回 JSON 对象。"
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
        row_by_code = {row.get("intent_code"): row for row in nodes}
        row_by_id = {str(row["id"]): row for row in nodes}
        matches = []
        for item in parsed.get("matches") or []:
            if not isinstance(item, dict):
                continue
            row = row_by_code.get(item.get("intentCode") or item.get("intent_code"))
            if row is None:
                row = row_by_id.get(str(item.get("intentId") or item.get("intent_id") or ""))
            if row is None:
                continue
            confidence = self._normalize_confidence(item.get("confidence"))
            if confidence < self.threshold:
                continue
            matches.append(self._to_match(row, confidence, reason=item.get("reason")))
        if not matches:
            return None
        matches = sorted(matches, key=lambda item: item.confidence, reverse=True)[:3]
        guidance = parsed.get("guidancePrompt") or parsed.get("guidance_prompt")
        return IntentResolution(matches=matches, guidance_prompt=guidance or self._guidance(matches))

    @staticmethod
    def _normalize_confidence(value: object) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return 0.0
        return min(max(number, 0.0), 1.0)
