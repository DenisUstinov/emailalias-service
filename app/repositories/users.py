import uuid
from typing import Any, cast

from sqlalchemy import func, select, update

from app.models.domain import User, UserRole


class UserRepository:
    def __init__(self, session) -> None:
        self.session = session

    async def create(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def get_by_id(self, user_id: uuid.UUID) -> User:
        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(
            User.email == email,
            User.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email_for_update(self, email: str) -> User | None:
        stmt = (
            select(User)
            .where(
                User.email == email,
                User.deleted_at.is_(None),
            )
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email_including_deleted_for_update(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email).with_for_update()
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id_for_update(self, user_id: uuid.UUID) -> User | None:
        stmt = (
            select(User)
            .where(
                User.id == user_id,
                User.deleted_at.is_(None),
            )
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete(self, user_id: uuid.UUID) -> int:
        stmt = (
            update(User)
            .where(User.id == user_id, User.deleted_at.is_(None))
            .values(deleted_at=func.now())
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount

    async def update(
        self,
        user_id: uuid.UUID,
        email: str | None = None,
        password_hash: str | None = None,
        is_banned: bool | None = None,
        role: UserRole | None = None,
    ) -> User:
        update_data: dict[str, Any] = {}
        if email is not None:
            update_data["email"] = email
        if password_hash is not None:
            update_data["password_hash"] = password_hash
        if is_banned is not None:
            update_data["is_banned"] = is_banned
        if role is not None:
            update_data["role"] = role

        stmt = (
            update(User)
            .where(
                User.id == user_id,
                User.deleted_at.is_(None),
            )
            .values(**update_data, updated_at=func.now())
            .returning(User)
        )
        result = await self.session.execute(stmt)
        updated_user = cast(User, result.scalars().one())
        return updated_user

    async def reactivate(self, user_id: uuid.UUID, password_hash: str) -> User:
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(
                password_hash=password_hash,
                deleted_at=None,
                updated_at=func.now(),
            )
            .returning(User)
        )
        result = await self.session.execute(stmt)
        return cast(User, result.scalars().one())
