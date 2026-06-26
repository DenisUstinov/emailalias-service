import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import insert, select

from app.core.config import settings
from app.core.exceptions import (
    AliasDomainNotFoundError,
    AliasMonthlyLimitExceededError,
    AliasPremiumDomainRequiresSubscriptionError,
)
from app.models.domain import Alias, AliasStatus, UserRole
from app.schemas.responses import AliasCreateResponse


@pytest.mark.anyio
class TestCreateAlias:
    async def test_success_creates_alias(
        self,
        http_client: AsyncClient,
        db_session,
        create_test_domain,
        authenticated_headers,
    ) -> None:
        domain = await create_test_domain(fqdn="success-test.com", is_default=True)
        headers = await authenticated_headers()

        payload = {"domain_id": str(domain.id), "local_part": "newsletter"}
        response = await http_client.post("/api/v1/aliases", json=payload, headers=headers)

        assert response.status_code == 201
        data = AliasCreateResponse(**response.json())
        assert data.id is not None
        assert data.email.endswith("@success-test.com")
        assert data.email.startswith("newsletter.")
        assert data.created_at is not None

        result = await db_session.execute(select(Alias).where(Alias.id == data.id))
        created_alias = result.scalar_one_or_none()
        assert created_alias is not None
        assert created_alias.status == AliasStatus.PENDING
        assert created_alias.local_part == "newsletter"

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
        assert data["status"] == 404
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
        assert data["status"] == 403
        assert data["detail"] == AliasPremiumDomainRequiresSubscriptionError().detail
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["instance"], str)

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
        assert data["status"] == 402
        assert data["detail"] == AliasMonthlyLimitExceededError().detail
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["instance"], str)
