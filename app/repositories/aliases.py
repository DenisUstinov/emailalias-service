import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, text, update

from app.models.domain import Alias, AliasStatus


class AliasRepository:
    def __init__(self, session) -> None:
        self.session = session

    async def create(self, alias: Alias) -> Alias:
        self.session.add(alias)
        await self.session.flush()
        await self.session.refresh(alias)
        return alias

    async def count_created_in_window(self, user_id: uuid.UUID, window_days: int) -> int:
        lock_key = f"alias_limit:{user_id}"
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": lock_key}
        )

        cutoff = datetime.now(UTC) - timedelta(days=window_days)
        stmt = select(func.count(Alias.id)).where(
            Alias.user_id == user_id,
            Alias.created_at >= cutoff,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_by_id(self, alias_id: uuid.UUID) -> Alias:
        stmt = select(Alias).where(Alias.id == alias_id)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def update_status(self, alias_id: uuid.UUID, status: AliasStatus) -> None:
        alias = await self.get_by_id(alias_id)
        alias.status = status
        await self.session.flush()

    async def get_active_alias_ids_by_user(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        stmt = select(Alias.id).where(
            Alias.user_id == user_id,
            Alias.status == AliasStatus.ACTIVE,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_aliases_by_user(self, user_id: uuid.UUID) -> list[Alias]:
        stmt = (
            select(Alias)
            .where(
                Alias.user_id == user_id,
                Alias.status != AliasStatus.DELETED,
            )
            .order_by(Alias.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete(self, alias_id: uuid.UUID, user_id: uuid.UUID) -> int:
        stmt = (
            update(Alias)
            .where(
                Alias.id == alias_id,
                Alias.user_id == user_id,
            )
            .values(status=AliasStatus.DELETED, updated_at=func.now())
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount
