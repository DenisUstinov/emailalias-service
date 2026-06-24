from sqlalchemy import select

from app.models.domain import Domain


class DomainRepository:
    def __init__(self, session) -> None:
        self.session = session

    async def get_all(self) -> list[Domain]:
        stmt = select(Domain)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
