import pytest
from httpx import AsyncClient

from app.models.domain import Domain, UserRole
from app.schemas.responses import DomainResponse


@pytest.mark.anyio
class TestGetDomains:
    async def test_success_returns_domains(
        self,
        http_client: AsyncClient,
        db_session,
        authenticated_headers,
    ) -> None:
        domain1 = Domain(fqdn="default.com", is_default=True)
        domain2 = Domain(fqdn="custom.com", is_default=False)
        db_session.add_all([domain1, domain2])
        await db_session.flush()

        headers = await authenticated_headers(role=UserRole.USER)
        response = await http_client.get("/api/v1/domains", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2

        domains = [DomainResponse(**item) for item in data]
        fqdns = {d.fqdn for d in domains}
        assert "default.com" in fqdns
        assert "custom.com" in fqdns

        default_domain = next(d for d in domains if d.fqdn == "default.com")
        assert default_domain.is_default is True

        custom_domain = next(d for d in domains if d.fqdn == "custom.com")
        assert custom_domain.is_default is False

    async def test_success_returns_empty_list_if_no_domains(
        self,
        http_client: AsyncClient,
        authenticated_headers,
    ) -> None:
        headers = await authenticated_headers(role=UserRole.USER)
        response = await http_client.get("/api/v1/domains", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    async def test_auth_error_unauthorized(
        self,
        http_client: AsyncClient,
    ) -> None:
        response = await http_client.get("/api/v1/domains")

        assert response.status_code == 401
        data = response.json()
        assert isinstance(data["status"], int)
        assert data["status"] == 401
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["detail"], str)
        assert isinstance(data["instance"], str)

    async def test_auth_error_admin_forbidden(
        self,
        http_client: AsyncClient,
        authenticated_headers,
    ) -> None:
        headers = await authenticated_headers(role=UserRole.ADMIN)
        response = await http_client.get("/api/v1/domains", headers=headers)

        assert response.status_code == 403
        data = response.json()
        assert isinstance(data["status"], int)
        assert data["status"] == 403
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["detail"], str)
        assert isinstance(data["instance"], str)
