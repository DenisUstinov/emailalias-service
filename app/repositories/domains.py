import uuid

from sqlalchemy import select

from app.models.domain import Domain


class DomainRepository:
    def __init__(self, session) -> None:
        self.session = session

    async def get_all(self) -> list[Domain]:
        stmt = select(Domain)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, domain_id: uuid.UUID) -> Domain:
        stmt = select(Domain).where(Domain.id == domain_id)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_by_id_for_update(self, domain_id: uuid.UUID) -> Domain | None:
        stmt = select(Domain).where(Domain.id == domain_id).with_for_update()
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
