import pytest
from httpx import AsyncClient

from app.core.config import settings


@pytest.mark.anyio
class TestTokensRateLimits:
    async def test_rate_limit_for_create_token(
        self,
        http_client: AsyncClient,
        rate_limit_checker,
    ) -> None:
        limit = int(settings.RATE_LIMIT_TOKEN_CREATION.split("/")[0])
        payload = {"email": "test@example.com", "password": "TestP@ss123!"}
        await rate_limit_checker(http_client, "POST", "/api/v1/tokens", limit, payload)
