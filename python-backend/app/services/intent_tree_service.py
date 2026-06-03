from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.ids import generate_id
from app.core.exceptions import RagentException
from app.schemas.intent_tree import (
    IntentNodeBatchRequest,
    IntentNodeCreateRequest,
    IntentNodeTreeResponse,
    IntentNodeUpdateRequest,
)


class IntentTreeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_tree(self) -> list[IntentNodeTreeResponse]:
        result = await self.session.execute(
            text(
                f"""
                SELECT {self._columns()}
                FROM t_intent_node
                WHERE deleted = 0
                ORDER BY level ASC, sort_order ASC, create_time ASC
                """,
            ),
        )
        nodes = [self._map_node(row) for row in result.mappings().all()]
        by_code = {node.intentCode: node for node in nodes}
        roots: list[IntentNodeTreeResponse] = []
        for node in nodes:
            if node.parentCode and node.parentCode in by_code:
                by_code[node.parentCode].children.append(node)
                continue
            roots.append(node)
        return roots

    async def create_node(self, request: IntentNodeCreateRequest, user_id: str) -> str:
        node_id = generate_id()
        await self.session.execute(
            text(
                """
                INSERT INTO t_intent_node (
                    id, kb_id, intent_code, name, level, parent_code, description,
                    examples, collection_name, top_k, mcp_tool_id, kind, prompt_snippet,
                    prompt_template, param_prompt_template, sort_order, enabled, create_by, update_by
                )
                VALUES (
                    :id, :kb_id, :intent_code, :name, :level, :parent_code, :description,
                    :examples, :collection_name, :top_k, :mcp_tool_id, :kind, :prompt_snippet,
                    :prompt_template, :param_prompt_template, :sort_order, :enabled, :user_id, :user_id
                )
                """,
            ),
            {
                "id": node_id,
                "kb_id": request.kb_id,
                "intent_code": request.intent_code,
                "name": request.name,
                "level": request.level,
                "parent_code": request.parent_code,
                "description": request.description,
                "examples": self._examples_to_text(request.examples),
                "collection_name": None,
                "top_k": request.top_k,
                "mcp_tool_id": request.mcp_tool_id,
                "kind": request.kind if request.kind is not None else 0,
                "prompt_snippet": request.prompt_snippet,
                "prompt_template": request.prompt_template,
                "param_prompt_template": request.param_prompt_template,
                "sort_order": request.sort_order if request.sort_order is not None else 0,
                "enabled": request.enabled if request.enabled is not None else 1,
                "user_id": user_id,
            },
        )
        await self.session.commit()
        return node_id

    async def update_node(self, node_id: str, request: IntentNodeUpdateRequest, user_id: str) -> None:
        await self._get_node(node_id)
        values = request.model_dump(exclude_unset=True)
        if not values:
            return
        column_map = {
            "name": "name",
            "level": "level",
            "parent_code": "parent_code",
            "description": "description",
            "collection_name": "collection_name",
            "mcp_tool_id": "mcp_tool_id",
            "top_k": "top_k",
            "kind": "kind",
            "sort_order": "sort_order",
            "enabled": "enabled",
            "prompt_snippet": "prompt_snippet",
            "prompt_template": "prompt_template",
            "param_prompt_template": "param_prompt_template",
        }
        params: dict[str, object] = {"id": node_id, "user_id": user_id}
        assignments: list[str] = []
        if "examples" in values:
            params["examples"] = self._examples_to_text(values["examples"])
            assignments.append("examples = :examples")
        for field, column in column_map.items():
            if field not in values:
                continue
            params[field] = values[field]
            assignments.append(f"{column} = :{field}")
        if not assignments:
            return
        assignments.extend(["update_by = :user_id", "update_time = CURRENT_TIMESTAMP"])
        await self.session.execute(
            text(
                f"""
                UPDATE t_intent_node
                SET {", ".join(assignments)}
                WHERE id = :id AND deleted = 0
                """,
            ),
            params,
        )
        await self.session.commit()

    async def delete_node(self, node_id: str, user_id: str) -> None:
        await self._get_node(node_id)
        await self._soft_delete([node_id], user_id)

    async def batch_enable(self, request: IntentNodeBatchRequest, enabled: int, user_id: str) -> None:
        ids = self._normalize_ids(request.ids)
        if not ids:
            return
        await self.session.execute(
            text(
                """
                UPDATE t_intent_node
                SET enabled = :enabled,
                    update_by = :user_id,
                    update_time = CURRENT_TIMESTAMP
                WHERE id = ANY(:ids) AND deleted = 0
                """,
            ),
            {"ids": ids, "enabled": enabled, "user_id": user_id},
        )
        await self.session.commit()

    async def batch_delete(self, request: IntentNodeBatchRequest, user_id: str) -> None:
        await self._soft_delete(self._normalize_ids(request.ids), user_id)

    async def _get_node(self, node_id: str):
        result = await self.session.execute(
            text(
                f"""
                SELECT {self._columns()}
                FROM t_intent_node
                WHERE id = :id AND deleted = 0
                """,
            ),
            {"id": node_id},
        )
        row = result.mappings().first()
        if row is None:
            raise RagentException(message="意图节点不存在", code="INTENT_NODE_NOT_FOUND", status_code=404)
        return row

    async def _soft_delete(self, ids: list[str], user_id: str) -> None:
        if not ids:
            return
        await self.session.execute(
            text(
                """
                UPDATE t_intent_node
                SET deleted = 1,
                    update_by = :user_id,
                    update_time = CURRENT_TIMESTAMP
                WHERE id = ANY(:ids) AND deleted = 0
                """,
            ),
            {"ids": ids, "user_id": user_id},
        )
        await self.session.commit()

    @staticmethod
    def _columns() -> str:
        return """
            id, intent_code, name, level, parent_code, description, examples,
            collection_name, mcp_tool_id, top_k, kind, sort_order, enabled,
            prompt_snippet, prompt_template, param_prompt_template
        """

    @staticmethod
    def _map_node(row: Any) -> IntentNodeTreeResponse:
        return IntentNodeTreeResponse(
            id=str(row["id"]),
            intentCode=row["intent_code"],
            name=row["name"],
            level=row["level"],
            parentCode=row.get("parent_code"),
            description=row.get("description"),
            examples=row.get("examples"),
            collectionName=row.get("collection_name"),
            mcpToolId=row.get("mcp_tool_id"),
            topK=row.get("top_k"),
            kind=row.get("kind"),
            sortOrder=row.get("sort_order"),
            enabled=row.get("enabled"),
            promptSnippet=row.get("prompt_snippet"),
            promptTemplate=row.get("prompt_template"),
            paramPromptTemplate=row.get("param_prompt_template"),
        )

    @staticmethod
    def _examples_to_text(examples: list[str] | None) -> str | None:
        if examples is None:
            return None
        return "\n".join(item for item in examples if item)

    @staticmethod
    def _normalize_ids(ids: list[str | int]) -> list[str]:
        return [str(item) for item in ids]
