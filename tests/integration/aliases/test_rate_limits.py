import pytest
from httpx import AsyncClient

from app.core.config import settings


@pytest.mark.anyio
class TestAliasesRateLimits:
    async def test_rate_limit_for_create_alias(
        self,
        http_client: AsyncClient,
        authenticated_headers,
        rate_limit_checker,
    ) -> None:
        limit = int(settings.RATE_LIMIT_ALIAS_CREATION.split("/")[0])
        headers = await authenticated_headers()
        payload = {
            "domain_id": "00000000-0000-0000-0000-000000000000",
            "local_part": "test",
        }
        await rate_limit_checker(http_client, "POST", "/api/v1/aliases", limit, payload, headers)
