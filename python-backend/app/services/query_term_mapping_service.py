from math import ceil
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.ids import generate_id
from app.core.exceptions import RagentException
from app.schemas.query_term_mapping import (
    QueryTermMappingPageResponse,
    QueryTermMappingPayload,
    QueryTermMappingResponse,
)


class QueryTermMappingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_mappings(
        self,
        current: int = 1,
        size: int = 10,
        keyword: str | None = None,
    ) -> QueryTermMappingPageResponse:
        current = max(current, 1)
        size = max(min(size, 200), 1)
        params: dict[str, object] = {"limit": size, "offset": (current - 1) * size}
        where = ["deleted = 0"]
        if keyword:
            where.append("(source_term ILIKE :keyword OR target_term ILIKE :keyword OR remark ILIKE :keyword)")
            params["keyword"] = f"%{keyword}%"
        where_sql = " AND ".join(where)
        total = await self.session.scalar(
            text(f"SELECT COUNT(*) FROM t_query_term_mapping WHERE {where_sql}"),
            params,
        )
        result = await self.session.execute(
            text(
                f"""
                SELECT id, source_term, target_term, match_type, priority, enabled, remark, create_time, update_time
                FROM t_query_term_mapping
                WHERE {where_sql}
                ORDER BY priority ASC, create_time DESC
                LIMIT :limit OFFSET :offset
                """,
            ),
            params,
        )
        total_count = int(total or 0)
        return QueryTermMappingPageResponse(
            records=[self._map_mapping(row) for row in result.mappings().all()],
            total=total_count,
            size=size,
            current=current,
            pages=ceil(total_count / size) if total_count else 0,
        )

    async def create_mapping(self, request: QueryTermMappingPayload, user_id: str) -> str:
        if not request.source_term or not request.target_term:
            raise RagentException(message="源词和目标词不能为空", code="MAPPING_TERM_REQUIRED", status_code=400)
        mapping_id = generate_id()
        await self.session.execute(
            text(
                """
                INSERT INTO t_query_term_mapping (
                    id, source_term, target_term, match_type, priority, enabled, remark, create_by, update_by
                )
                VALUES (
                    :id, :source_term, :target_term, :match_type, :priority, :enabled, :remark, :user_id, :user_id
                )
                """,
            ),
            {
                "id": mapping_id,
                "source_term": request.source_term,
                "target_term": request.target_term,
                "match_type": request.match_type if request.match_type is not None else 1,
                "priority": request.priority if request.priority is not None else 100,
                "enabled": 1 if request.enabled is None or request.enabled else 0,
                "remark": request.remark,
                "user_id": user_id,
            },
        )
        await self.session.commit()
        return mapping_id

    async def get_mapping(self, mapping_id: str) -> QueryTermMappingResponse:
        return self._map_mapping(await self._get_mapping(mapping_id))

    async def update_mapping(self, mapping_id: str, request: QueryTermMappingPayload, user_id: str) -> None:
        await self._get_mapping(mapping_id)
        values = request.model_dump(exclude_unset=True)
        if not values:
            return
        column_map = {
            "source_term": "source_term",
            "target_term": "target_term",
            "match_type": "match_type",
            "priority": "priority",
            "enabled": "enabled",
            "remark": "remark",
        }
        params: dict[str, object] = {"id": mapping_id, "user_id": user_id}
        assignments: list[str] = []
        for field, column in column_map.items():
            if field not in values:
                continue
            if field == "enabled":
                params[field] = 1 if values[field] else 0
            else:
                params[field] = values[field]
            assignments.append(f"{column} = :{field}")
        assignments.extend(["update_by = :user_id", "update_time = CURRENT_TIMESTAMP"])
        await self.session.execute(
            text(
                f"""
                UPDATE t_query_term_mapping
                SET {", ".join(assignments)}
                WHERE id = :id AND deleted = 0
                """,
            ),
            params,
        )
        await self.session.commit()

    async def delete_mapping(self, mapping_id: str, user_id: str) -> None:
        await self._get_mapping(mapping_id)
        await self.session.execute(
            text(
                """
                UPDATE t_query_term_mapping
                SET deleted = 1, update_by = :user_id, update_time = CURRENT_TIMESTAMP
                WHERE id = :id AND deleted = 0
                """,
            ),
            {"id": mapping_id, "user_id": user_id},
        )
        await self.session.commit()

    async def _get_mapping(self, mapping_id: str):
        result = await self.session.execute(
            text(
                """
                SELECT id, source_term, target_term, match_type, priority, enabled, remark, create_time, update_time
                FROM t_query_term_mapping
                WHERE id = :id AND deleted = 0
                """,
            ),
            {"id": mapping_id},
        )
        row = result.mappings().first()
        if row is None:
            raise RagentException(message="查询词映射不存在", code="MAPPING_NOT_FOUND", status_code=404)
        return row

    @staticmethod
    def _map_mapping(row: Any) -> QueryTermMappingResponse:
        return QueryTermMappingResponse(
            id=str(row["id"]),
            sourceTerm=row["source_term"],
            targetTerm=row["target_term"],
            matchType=row["match_type"],
            priority=row["priority"],
            enabled=bool(row["enabled"]),
            remark=row.get("remark"),
            createTime=row.get("create_time"),
            updateTime=row.get("update_time"),
        )
