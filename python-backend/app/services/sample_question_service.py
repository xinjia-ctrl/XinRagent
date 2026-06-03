from math import ceil
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.ids import generate_id
from app.core.exceptions import RagentException
from app.schemas.sample_question import (
    SampleQuestionPageResponse,
    SampleQuestionPayload,
    SampleQuestionResponse,
)


class SampleQuestionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_public_questions(self) -> list[SampleQuestionResponse]:
        result = await self.session.execute(
            text(
                """
                SELECT id, title, description, question, create_time, update_time
                FROM t_sample_question
                WHERE deleted = 0
                ORDER BY create_time DESC
                """,
            ),
        )
        return [self._map_question(row) for row in result.mappings().all()]

    async def list_questions(
        self,
        current: int = 1,
        size: int = 10,
        keyword: str | None = None,
    ) -> SampleQuestionPageResponse:
        current = max(current, 1)
        size = max(min(size, 200), 1)
        params: dict[str, object] = {"limit": size, "offset": (current - 1) * size}
        where = ["deleted = 0"]
        if keyword:
            where.append("(title ILIKE :keyword OR description ILIKE :keyword OR question ILIKE :keyword)")
            params["keyword"] = f"%{keyword}%"
        where_sql = " AND ".join(where)
        total = await self.session.scalar(
            text(f"SELECT COUNT(*) FROM t_sample_question WHERE {where_sql}"),
            params,
        )
        result = await self.session.execute(
            text(
                f"""
                SELECT id, title, description, question, create_time, update_time
                FROM t_sample_question
                WHERE {where_sql}
                ORDER BY create_time DESC
                LIMIT :limit OFFSET :offset
                """,
            ),
            params,
        )
        total_count = int(total or 0)
        return SampleQuestionPageResponse(
            records=[self._map_question(row) for row in result.mappings().all()],
            total=total_count,
            size=size,
            current=current,
            pages=ceil(total_count / size) if total_count else 0,
        )

    async def create_question(self, request: SampleQuestionPayload) -> str:
        if not request.question:
            raise RagentException(message="示例问题不能为空", code="SAMPLE_QUESTION_REQUIRED", status_code=400)
        question_id = generate_id()
        await self.session.execute(
            text(
                """
                INSERT INTO t_sample_question (id, title, description, question)
                VALUES (:id, :title, :description, :question)
                """,
            ),
            {
                "id": question_id,
                "title": request.title,
                "description": request.description,
                "question": request.question,
            },
        )
        await self.session.commit()
        return question_id

    async def update_question(self, question_id: str, request: SampleQuestionPayload) -> None:
        await self._get_question(question_id)
        values = request.model_dump(exclude_unset=True)
        if not values:
            return
        params: dict[str, object] = {"id": question_id}
        assignments: list[str] = []
        for field in ("title", "description", "question"):
            if field not in values:
                continue
            params[field] = values[field]
            assignments.append(f"{field} = :{field}")
        assignments.append("update_time = CURRENT_TIMESTAMP")
        await self.session.execute(
            text(
                f"""
                UPDATE t_sample_question
                SET {", ".join(assignments)}
                WHERE id = :id AND deleted = 0
                """,
            ),
            params,
        )
        await self.session.commit()

    async def delete_question(self, question_id: str) -> None:
        await self._get_question(question_id)
        await self.session.execute(
            text(
                """
                UPDATE t_sample_question
                SET deleted = 1, update_time = CURRENT_TIMESTAMP
                WHERE id = :id AND deleted = 0
                """,
            ),
            {"id": question_id},
        )
        await self.session.commit()

    async def _get_question(self, question_id: str):
        result = await self.session.execute(
            text(
                """
                SELECT id
                FROM t_sample_question
                WHERE id = :id AND deleted = 0
                """,
            ),
            {"id": question_id},
        )
        row = result.mappings().first()
        if row is None:
            raise RagentException(message="示例问题不存在", code="SAMPLE_QUESTION_NOT_FOUND", status_code=404)
        return row

    @staticmethod
    def _map_question(row: Any) -> SampleQuestionResponse:
        return SampleQuestionResponse(
            id=str(row["id"]),
            title=row.get("title"),
            description=row.get("description"),
            question=row["question"],
            createTime=row.get("create_time"),
            updateTime=row.get("update_time"),
        )
