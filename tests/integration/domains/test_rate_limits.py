import pytest
from httpx import AsyncClient

from app.core.config import settings


@pytest.mark.anyio
class TestDomainsRateLimits:
    async def test_rate_limit_for_get_domains(
        self,
        http_client: AsyncClient,
        authenticated_headers,
        rate_limit_checker,
    ) -> None:
        limit = int(settings.RATE_LIMIT_DOMAINS.split("/")[0])
        headers = await authenticated_headers()
        await rate_limit_checker(http_client, "GET", "/api/v1/domains", limit, headers=headers)
