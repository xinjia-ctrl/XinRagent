from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import IntentNode
from app.repositories.base import BaseRepository


class IntentNodeRepository(BaseRepository[IntentNode]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, IntentNode)

    async def list_enabled(self) -> Sequence[IntentNode]:
        statement = (
            select(IntentNode)
            .where(IntentNode.enabled.is_(True))
            .order_by(IntentNode.sort_order.asc())
        )
        result = await self.session.scalars(statement)
        return result.all()
