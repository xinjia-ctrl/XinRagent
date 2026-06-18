from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RagTraceNode, RagTraceRun
from app.repositories.base import BaseRepository


class RagTraceRunRepository(BaseRepository[RagTraceRun]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, RagTraceRun)


class RagTraceNodeRepository(BaseRepository[RagTraceNode]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, RagTraceNode)

    async def list_by_run(self, trace_id: str) -> Sequence[RagTraceNode]:
        statement = select(RagTraceNode).where(RagTraceNode.trace_id == trace_id)
        result = await self.session.scalars(statement)
        return result.all()
