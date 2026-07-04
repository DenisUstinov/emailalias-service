import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import Alias, AliasStatus, Domain, User, UserRole


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
def make_domain() -> Callable[..., Domain]:
    def _factory(
        domain_id: uuid.UUID | None = None,
        fqdn: str = "example.com",
        is_default: bool = True,
    ) -> Domain:
        return Domain(
            id=domain_id or uuid.uuid4(),
            fqdn=fqdn,
            is_default=is_default,
        )

    return _factory


@pytest.fixture
def make_alias() -> Callable[..., Alias]:
    def _factory(
        alias_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        domain_id: uuid.UUID | None = None,
        local_part: str = "test",
        random_part: str = "abc123",
        status: AliasStatus = AliasStatus.PENDING,
    ) -> Alias:
        return Alias(
            id=alias_id or uuid.uuid4(),
            user_id=user_id or uuid.uuid4(),
            domain_id=domain_id or uuid.uuid4(),
            local_part=local_part,
            random_part=random_part,
            status=status,
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
