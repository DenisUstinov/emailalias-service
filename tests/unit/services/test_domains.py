import uuid
from unittest.mock import AsyncMock

import pytest

from app.models.domain import Domain
from app.schemas.responses import DomainResponse
from app.services.domains import DomainService


@pytest.mark.anyio
class TestDomainServiceGetDomains:
    async def test_success_returns_mapped_domains(self) -> None:
        domain_repo_mock = AsyncMock()

        domain1 = Domain(
            id=uuid.uuid4(),
            fqdn="default.com",
            is_default=True,
        )
        domain2 = Domain(
            id=uuid.uuid4(),
            fqdn="custom.com",
            is_default=False,
        )
        domain_repo_mock.get_all.return_value = [domain1, domain2]

        service = DomainService(domain_repo=domain_repo_mock)
        result = await service.get_domains()

        assert len(result) == 2
        assert all(isinstance(item, DomainResponse) for item in result)

        assert result[0].id == domain1.id
        assert result[0].fqdn == "default.com"
        assert result[0].is_default is True

        assert result[1].id == domain2.id
        assert result[1].fqdn == "custom.com"
        assert result[1].is_default is False

        domain_repo_mock.get_all.assert_awaited_once()

    async def test_success_returns_empty_list_when_no_domains(self) -> None:
        domain_repo_mock = AsyncMock()
        domain_repo_mock.get_all.return_value = []

        service = DomainService(domain_repo=domain_repo_mock)
        result = await service.get_domains()

        assert result == []
        domain_repo_mock.get_all.assert_awaited_once()

    async def test_raises_exception_when_repository_fails(self) -> None:
        domain_repo_mock = AsyncMock()
        domain_repo_mock.get_all.side_effect = Exception("Database connection failed")

        service = DomainService(domain_repo=domain_repo_mock)

        with pytest.raises(Exception, match="Database connection failed"):
            await service.get_domains()
