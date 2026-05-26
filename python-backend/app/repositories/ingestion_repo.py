from sqlalchemy.ext.asyncio import AsyncSession


class IngestionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
