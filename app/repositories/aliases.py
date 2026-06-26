import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.models.domain import Alias


class AliasRepository:
    def __init__(self, session) -> None:
        self.session = session

    async def create(self, alias: Alias) -> Alias:
        self.session.add(alias)
        await self.session.flush()
        await self.session.refresh(alias)
        return alias

    async def count_created_in_window(self, user_id: uuid.UUID, window_days: int) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=window_days)
        stmt = select(func.count(Alias.id)).where(
            Alias.user_id == user_id,
            Alias.created_at >= cutoff,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()
