import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import Domain, User, UserRole


@pytest.fixture
def make_user() -> Callable[..., User]:
    def _factory(
        user_id: uuid.UUID | None = None,
        email: str = "test@example.com",
        password_hash: str = "$argon2id$hashed",
        role: UserRole = UserRole.USER,
        is_banned: bool = False,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> User:
        now = created_at or datetime.now(UTC)
        return User(
            id=user_id or uuid.uuid4(),
            email=email,
            password_hash=password_hash,
            role=role,
            is_banned=is_banned,
            created_at=now,
            updated_at=updated_at or now,
        )

    return _factory


@pytest.fixture
async def create_test_domain(
    db_session: AsyncSession,
) -> Callable[..., Awaitable[Domain]]:
    async def _create(
        fqdn: str,
        is_default: bool = False,
    ) -> Domain:
        domain = Domain(fqdn=fqdn, is_default=is_default)
        db_session.add(domain)
        await db_session.flush()
        return domain

    return _create
