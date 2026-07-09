import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from freezegun import freeze_time
from httpx import AsyncClient
from sqlalchemy import insert, select

from app.api.v1.endpoints import aliases
from app.core.config import settings
from app.core.exceptions import (
    AliasActiveLimitExceededError,
    AliasCollisionError,
    AliasDomainNotFoundError,
    AliasMonthlyLimitExceededError,
    AliasPremiumDomainRequiresSubscriptionError,
)
from app.models.domain import Alias, AliasStatus, UserRole
from app.schemas.responses import AliasCreateResponse
from app.services import aliases as aliases_service_module


@pytest.mark.anyio
class TestCreateAlias:
    async def test_success_creates_alias_and_queues_task(
        self,
        http_client: AsyncClient,
        db_session,
        create_test_domain,
        authenticated_headers,
        monkeypatch,
    ) -> None:
        mock_task = MagicMock()
        monkeypatch.setattr(aliases, "provision_alias_task", mock_task)

        domain = await create_test_domain(fqdn="success-test.com", is_default=True)
        headers = await authenticated_headers()

        payload = {"domain_id": str(domain.id), "local_part": "newsletter"}
        response = await http_client.post("/api/v1/aliases", json=payload, headers=headers)

        assert response.status_code == 202
        data = AliasCreateResponse(**response.json())
        assert data.id is not None
        assert data.status == "pending"
        assert data.email.endswith("@success-test.com")
        assert data.email.startswith("newsletter.")
        assert data.created_at is not None

        mock_task.apply_async.assert_called_once()
        call_args = mock_task.apply_async.call_args
        assert call_args[1]["args"][0] == str(data.id)

        result = await db_session.execute(select(Alias).where(Alias.id == data.id))
        created_alias = result.scalar_one_or_none()
        assert created_alias is not None
        assert created_alias.status == AliasStatus.PENDING
        assert created_alias.local_part == "newsletter"

    async def test_business_error_collision(
        self,
        http_client: AsyncClient,
        db_session,
        create_test_domain,
        create_test_user,
        authenticated_headers,
        monkeypatch,
    ) -> None:
        domain = await create_test_domain(fqdn="collision-test.com", is_default=True)
        user = await create_test_user(password="TestP@ss123!")
        headers = await authenticated_headers()

        stmt = insert(Alias).values(
            user_id=user.id,
            domain_id=domain.id,
            local_part="duplicate",
            random_part="abc123",
            status=AliasStatus.ACTIVE,
        )
        await db_session.execute(stmt)
        await db_session.flush()

        monkeypatch.setattr(
            aliases_service_module.AliasService,
            "_generate_random_part",
            staticmethod(lambda: "abc123"),
        )

        payload = {"domain_id": str(domain.id), "local_part": "duplicate"}
        response = await http_client.post("/api/v1/aliases", json=payload, headers=headers)

        assert response.status_code == 409
        data = response.json()
        assert isinstance(data["status"], int)
        assert data["status"] == 409
        assert isinstance(data["detail"], str)
        assert data["detail"] == AliasCollisionError().detail
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["instance"], str)

    @pytest.mark.parametrize(
        "payload",
        [
            {"domain_id": "invalid-uuid", "local_part": "test"},
            {"local_part": "test"},
            {"domain_id": str(uuid.uuid4())},
            {"domain_id": str(uuid.uuid4()), "local_part": "a" * 100},
            {"domain_id": str(uuid.uuid4()), "local_part": "invalid space"},
            {"domain_id": str(uuid.uuid4()), "local_part": "ends.dot."},
        ],
    )
    async def test_validation_errors_invalid_payload(
        self, http_client: AsyncClient, authenticated_headers, payload: dict
    ) -> None:
        headers = await authenticated_headers()
        response = await http_client.post("/api/v1/aliases", json=payload, headers=headers)

        assert response.status_code == 422
        data = response.json()
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["status"], int)
        assert data["status"] == 422
        assert isinstance(data["detail"], str)
        assert isinstance(data["instance"], str)
        assert isinstance(data["field_errors"], list)

    async def test_auth_error_unauthorized(
        self,
        http_client: AsyncClient,
    ) -> None:
        response = await http_client.post(
            "/api/v1/aliases",
            json={"domain_id": str(uuid.uuid4()), "local_part": "test"},
        )

        assert response.status_code == 401
        data = response.json()
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["status"], int)
        assert data["status"] == 401
        assert isinstance(data["detail"], str)
        assert isinstance(data["instance"], str)

    async def test_business_error_domain_not_found(
        self,
        http_client: AsyncClient,
        authenticated_headers,
    ) -> None:
        headers = await authenticated_headers()
        payload = {"domain_id": str(uuid.uuid4()), "local_part": "test"}
        response = await http_client.post("/api/v1/aliases", json=payload, headers=headers)

        assert response.status_code == 404
        data = response.json()
        assert isinstance(data["status"], int)
        assert data["status"] == 404
        assert isinstance(data["detail"], str)
        assert data["detail"] == AliasDomainNotFoundError().detail
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["instance"], str)

    async def test_business_error_premium_domain_requires_subscription(
        self,
        http_client: AsyncClient,
        create_test_domain,
        authenticated_headers,
    ) -> None:
        premium_domain = await create_test_domain(fqdn="premium.com", is_default=False)
        headers = await authenticated_headers()
        payload = {"domain_id": str(premium_domain.id), "local_part": "vip"}
        response = await http_client.post("/api/v1/aliases", json=payload, headers=headers)

        assert response.status_code == 403
        data = response.json()
        assert isinstance(data["status"], int)
        assert data["status"] == 403
        assert isinstance(data["detail"], str)
        assert data["detail"] == AliasPremiumDomainRequiresSubscriptionError().detail
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["instance"], str)

    @freeze_time("2026-01-01T12:00:00Z")
    async def test_business_error_monthly_limit_exceeded(
        self,
        http_client: AsyncClient,
        db_session,
        create_test_user,
        create_auth_token,
        create_test_domain,
    ) -> None:
        domain = await create_test_domain(fqdn="limit-test.com", is_default=True)
        user = await create_test_user(password="TestP@ss123!")
        token = await create_auth_token(user_id=user.id, role=UserRole.USER)
        headers = {"Authorization": f"Bearer {token}"}

        for i in range(settings.ALIAS_FREE_TIER_MONTHLY_LIMIT):
            stmt = insert(Alias).values(
                user_id=user.id,
                domain_id=domain.id,
                local_part=f"pre{i}",
                random_part="aaaaaa",
                status=AliasStatus.ACTIVE,
                created_at=datetime.now(UTC),
            )
            await db_session.execute(stmt)
        await db_session.flush()

        payload = {"domain_id": str(domain.id), "local_part": "overflow"}
        response = await http_client.post("/api/v1/aliases", json=payload, headers=headers)

        assert response.status_code == 402
        data = response.json()
        assert isinstance(data["status"], int)
        assert data["status"] == 402
        assert isinstance(data["detail"], str)
        assert data["detail"] == AliasMonthlyLimitExceededError().detail
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["instance"], str)

    async def test_business_error_active_limit_exceeded(
        self,
        http_client: AsyncClient,
        db_session,
        create_test_user,
        create_auth_token,
        create_test_domain,
    ) -> None:
        domain = await create_test_domain(fqdn="active-limit-test.com", is_default=True)
        user = await create_test_user(password="TestP@ss123!")
        token = await create_auth_token(user_id=user.id, role=UserRole.USER)
        headers = {"Authorization": f"Bearer {token}"}

        for i in range(settings.ALIAS_FREE_TIER_ACTIVE_LIMIT):
            stmt = insert(Alias).values(
                user_id=user.id,
                domain_id=domain.id,
                local_part=f"active{i}",
                random_part=f"act{i:03d}",
                status=AliasStatus.ACTIVE,
            )
            await db_session.execute(stmt)
        await db_session.flush()

        payload = {"domain_id": str(domain.id), "local_part": "overflow"}
        response = await http_client.post("/api/v1/aliases", json=payload, headers=headers)

        assert response.status_code == 402
        data = response.json()
        assert isinstance(data["status"], int)
        assert data["status"] == 402
        assert isinstance(data["detail"], str)
        assert data["detail"] == AliasActiveLimitExceededError().detail
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["instance"], str)
