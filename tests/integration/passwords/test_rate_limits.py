import pytest
from httpx import AsyncClient

from app.core.config import settings


@pytest.mark.anyio
class TestPasswordsRateLimits:
    async def test_rate_limit_for_update_password(
        self,
        http_client: AsyncClient,
        rate_limit_checker,
    ) -> None:
        limit = int(settings.RATE_LIMIT_PASSWORD_UPDATE.split("/")[0])
        payload = {
            "email": "test@example.com",
            "new_password": "TestP@ss123!",
            "verification_token": "a" * 43,
        }
        await rate_limit_checker(http_client, "PATCH", "/api/v1/passwords", limit, payload)
