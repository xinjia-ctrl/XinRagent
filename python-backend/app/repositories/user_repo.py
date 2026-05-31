from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, User)

    async def get_by_username(self, username: str) -> User | None:
        statement = select(User).where(User.username == username, User.deleted == 0)
        return await self.session.scalar(statement)

    async def list_page(
        self,
        *,
        current: int = 1,
        size: int = 10,
        keyword: str | None = None,
    ) -> tuple[Sequence[User], int]:
        current = max(current, 1)
        size = max(min(size, 100), 1)
        conditions = [User.deleted == 0]
        if keyword:
            conditions.append(User.username.ilike(f"%{keyword}%"))

        total_statement = select(func.count()).select_from(User).where(*conditions)
        total = await self.session.scalar(total_statement) or 0

        statement = (
            select(User)
            .where(*conditions)
            .order_by(User.create_time.desc().nullslast(), User.id.desc())
            .offset((current - 1) * size)
            .limit(size)
        )
        result = await self.session.scalars(statement)
        return result.all(), total

    async def username_exists(self, username: str, exclude_id: str | None = None) -> bool:
        conditions = [User.username == username, User.deleted == 0]
        if exclude_id is not None:
            conditions.append(User.id != exclude_id)
        statement = select(func.count()).select_from(User).where(*conditions)
        return bool(await self.session.scalar(statement))
