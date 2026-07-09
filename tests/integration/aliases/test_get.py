from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from app.models.domain import Alias, AliasStatus, UserRole
from app.schemas.responses import AliasListItemResponse


@pytest.mark.anyio
class TestGetAliases:
    async def test_success_returns_aliases_sorted_by_created_at(
        self,
        http_client: AsyncClient,
        db_session,
        create_test_user,
        create_test_domain,
        create_auth_token,
    ) -> None:
        user = await create_test_user(password="TestP@ss123!")
        domain = await create_test_domain(fqdn="get-test.com", is_default=True)
        token = await create_auth_token(user_id=user.id, role=UserRole.USER)
        headers = {"Authorization": f"Bearer {token}"}

        now = datetime.now(UTC)

        alias_active = Alias(
            user_id=user.id,
            domain_id=domain.id,
            local_part="active",
            random_part="abc123",
            status=AliasStatus.ACTIVE,
            created_at=now - timedelta(minutes=2),
        )
        alias_pending = Alias(
            user_id=user.id,
            domain_id=domain.id,
            local_part="pending",
            random_part="def456",
            status=AliasStatus.PENDING,
            created_at=now - timedelta(minutes=1),
        )
        alias_failed = Alias(
            user_id=user.id,
            domain_id=domain.id,
            local_part="failed",
            random_part="ghi789",
            status=AliasStatus.FAILED,
            created_at=now,
        )

        db_session.add_all([alias_active, alias_pending, alias_failed])
        await db_session.flush()

        response = await http_client.get("/api/v1/aliases", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 3

        aliases = [AliasListItemResponse(**item) for item in data]

        assert aliases[0].id == alias_failed.id
        assert aliases[0].status == "failed"
        assert aliases[0].email == "failed.ghi789@get-test.com"

        assert aliases[1].id == alias_pending.id
        assert aliases[1].status == "pending"

        assert aliases[2].id == alias_active.id
        assert aliases[2].status == "active"

    async def test_success_excludes_deleted_aliases(
        self,
        http_client: AsyncClient,
        db_session,
        create_test_user,
        create_test_domain,
        create_auth_token,
    ) -> None:
        user = await create_test_user(password="TestP@ss123!")
        domain = await create_test_domain(fqdn="exclude-test.com", is_default=True)
        token = await create_auth_token(user_id=user.id, role=UserRole.USER)
        headers = {"Authorization": f"Bearer {token}"}

        alias_active = Alias(
            user_id=user.id,
            domain_id=domain.id,
            local_part="active",
            random_part="abc123",
            status=AliasStatus.ACTIVE,
        )
        alias_deleted = Alias(
            user_id=user.id,
            domain_id=domain.id,
            local_part="deleted",
            random_part="def456",
            status=AliasStatus.DELETED,
        )

        db_session.add_all([alias_active, alias_deleted])
        await db_session.flush()

        response = await http_client.get("/api/v1/aliases", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

        alias = AliasListItemResponse(**data[0])
        assert alias.id == alias_active.id
        assert alias.status == "active"

    async def test_success_isolates_user_data(
        self,
        http_client: AsyncClient,
        db_session,
        create_test_user,
        create_test_domain,
        create_auth_token,
    ) -> None:
        user1 = await create_test_user(password="TestP@ss123!")
        user2 = await create_test_user(password="TestP@ss123!")
        domain = await create_test_domain(fqdn="isolate-test.com", is_default=True)

        token1 = await create_auth_token(user_id=user1.id, role=UserRole.USER)
        headers1 = {"Authorization": f"Bearer {token1}"}

        alias_user1 = Alias(
            user_id=user1.id,
            domain_id=domain.id,
            local_part="user1",
            random_part="abc123",
            status=AliasStatus.ACTIVE,
        )
        alias_user2 = Alias(
            user_id=user2.id,
            domain_id=domain.id,
            local_part="user2",
            random_part="def456",
            status=AliasStatus.ACTIVE,
        )

        db_session.add_all([alias_user1, alias_user2])
        await db_session.flush()

        response = await http_client.get("/api/v1/aliases", headers=headers1)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

        alias = AliasListItemResponse(**data[0])
        assert alias.id == alias_user1.id

    async def test_success_returns_empty_list(
        self,
        http_client: AsyncClient,
        create_test_user,
        create_auth_token,
    ) -> None:
        user = await create_test_user(password="TestP@ss123!")
        token = await create_auth_token(user_id=user.id, role=UserRole.USER)
        headers = {"Authorization": f"Bearer {token}"}

        response = await http_client.get("/api/v1/aliases", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    async def test_auth_error_unauthorized(
        self,
        http_client: AsyncClient,
    ) -> None:
        response = await http_client.get("/api/v1/aliases")

        assert response.status_code == 401
        data = response.json()
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["status"], int)
        assert data["status"] == 401
        assert isinstance(data["detail"], str)
        assert isinstance(data["instance"], str)
